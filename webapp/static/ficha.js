/* Ficha de costeo de una matriz: grilla de insumos con edición en celda,
 * pestañas de filtro por tipo con subtotales y pie de precios editable. */
(function () {
    "use strict";

    const encabezado = document.getElementById("ficha-encabezado");
    const MATRIZ = encabezado.dataset.matriz;
    const CONCEPTO = encabezado.dataset.concepto || "";
    const SUFIJO = "?matriz=" + encodeURIComponent(MATRIZ) +
        "&concepto=" + encodeURIComponent(CONCEPTO);

    const cuerpo = document.getElementById("cuerpo-insumos");
    const cuerpoPie = document.getElementById("cuerpo-pie");
    const tabs = document.getElementById("tabs-tipos");
    const flash = document.getElementById("flash-js");

    let ficha = null;
    let filtro = "Todos";
    let expandidos = new Set();   // claves de compuestos abiertos

    function avisar(mensaje, esError) {
        flash.innerHTML = "";
        if (!mensaje) return;
        const p = document.createElement("p");
        p.className = "flash " + (esError ? "flash-error" : "flash-ok");
        p.textContent = mensaje;
        flash.appendChild(p);
        setTimeout(() => { if (p.parentNode) p.remove(); }, 6000);
    }

    async function llamar(url, metodo, datos) {
        const opciones = { method: metodo || "GET" };
        if (datos) {
            opciones.headers = { "Content-Type": "application/json" };
            opciones.body = JSON.stringify(datos);
        }
        const respuesta = await fetch(url, opciones);
        const json = await respuesta.json().catch(() => ({}));
        if (!respuesta.ok || json.ok === false) {
            throw new Error(json.error || ("Error " + respuesta.status));
        }
        return json;
    }

    // ------------------------------------------------------------ pintado
    function pintar(nuevaFicha, repintarTodo) {
        ficha = nuevaFicha;
        pintarEncabezado();
        pintarTabs();
        if (repintarTodo) {
            pintarInsumos();
            pintarPie(true);
        } else {
            actualizarCeldas();
            pintarPie(false);
        }
    }

    function pintarEncabezado() {
        const desc = document.getElementById("ficha-descripcion");
        if (document.activeElement !== desc) {
            desc.value = ficha.matriz.descripcion;
        }
        document.getElementById("ficha-unidad").textContent = ficha.matriz.unidad;
        document.getElementById("ficha-cd").textContent =
            "$ " + ficha.costo_directo_fmt;
        document.getElementById("ficha-pv").textContent =
            "$ " + ficha.precio_venta_fmt;

        if (ficha.concepto) {
            document.getElementById("chip-concepto").hidden = false;
            document.getElementById("ficha-concepto-info").textContent =
                ficha.concepto.clave + " × " + ficha.concepto.cantidad_fmt +
                " " + ficha.concepto.unidad + " = $ " + ficha.concepto.importe_fmt;
        }
        if (ficha.conceptos_vinculados.length) {
            document.getElementById("chip-vinculados").hidden = false;
            document.getElementById("ficha-vinculados").textContent =
                ficha.conceptos_vinculados.join(", ");
        }
    }

    function pintarTabs() {
        tabs.innerHTML = "";
        for (const sub of ficha.subtotales) {
            const btn = document.createElement("button");
            btn.type = "button";
            btn.className = "tab-tipo" + (filtro === sub.tipo ? " activa" : "");
            btn.innerHTML = "<span>" + sub.tipo + "</span><strong>$ " +
                sub.importe_fmt + "</strong>";
            btn.addEventListener("click", () => {
                filtro = sub.tipo;
                pintarTabs();
                aplicarFiltro();
            });
            tabs.appendChild(btn);
        }
    }

    function aplicarFiltro() {
        for (const tr of cuerpo.querySelectorAll("tr[data-clave]")) {
            const visible = filtro === "Todos" || tr.dataset.tipo === filtro;
            tr.style.display = visible ? "" : "none";
            if (!visible) continue;
            // Sub-filas de compuestos siguen a su padre.
            if (tr.classList.contains("fila-componente")) {
                tr.style.display = expandidos.has(tr.dataset.padre) ? "" : "none";
            }
        }
    }

    function pintarInsumos() {
        cuerpo.innerHTML = "";
        for (const insumo of ficha.insumos) {
            cuerpo.appendChild(construirFilaInsumo(insumo));
            for (const comp of insumo.componentes) {
                cuerpo.appendChild(construirFilaComponente(insumo, comp));
            }
        }
        aplicarFiltro();
    }

    function construirFilaInsumo(insumo) {
        const tr = document.createElement("tr");
        tr.dataset.clave = insumo.clave;
        tr.dataset.tipo = insumo.tipo;
        tr.className = "fila-insumo";

        const tdTipo = document.createElement("td");
        tdTipo.className = "col-tipo";
        const badge = document.createElement("span");
        badge.className = "badge badge-" +
            insumo.tipo.toLowerCase().replace(/[^a-z]/g, "");
        badge.textContent = insumo.tipo;
        tdTipo.appendChild(badge);
        tr.appendChild(tdTipo);

        const tdClave = document.createElement("td");
        tdClave.className = "col-clave";
        if (insumo.es_compuesto) {
            const flecha = document.createElement("span");
            flecha.className = "flecha";
            flecha.textContent = expandidos.has(insumo.clave) ? "▾" : "▸";
            flecha.title = "Ver componentes";
            flecha.addEventListener("click", () => {
                if (expandidos.has(insumo.clave)) expandidos.delete(insumo.clave);
                else expandidos.add(insumo.clave);
                flecha.textContent = expandidos.has(insumo.clave) ? "▾" : "▸";
                aplicarFiltro();
            });
            tdClave.appendChild(flecha);
        }
        const codigo = document.createElement("code");
        codigo.textContent = insumo.clave;
        tdClave.appendChild(codigo);
        tr.appendChild(tdClave);

        const tdDesc = document.createElement("td");
        tdDesc.className = "col-desc";
        tdDesc.textContent = insumo.descripcion;
        if (insumo.es_pct_mo) {
            tdDesc.textContent += " (% de la mano de obra)";
        }
        tr.appendChild(tdDesc);

        agregarCelda(tr, "col-unidad", insumo.unidad);

        // Cantidad / rendimiento: siempre editable.
        const tdCant = document.createElement("td");
        tdCant.className = "col-num";
        tdCant.appendChild(crearEditable(insumo.cantidad, (valor) =>
            llamar("/api/matriz/" + encodeURIComponent(MATRIZ) + "/insumo/" +
                encodeURIComponent(insumo.clave) + SUFIJO,
                "PATCH", { cantidad: valor })));
        tr.appendChild(tdCant);

        // Costo unitario: editable solo para recursos de costo capturado.
        const tdCosto = document.createElement("td");
        tdCosto.className = "col-num";
        if (insumo.costo_editable) {
            tdCosto.appendChild(crearEditable(insumo.costo, (valor) =>
                llamar("/api/recurso/" + encodeURIComponent(insumo.clave) + SUFIJO,
                    "PATCH", { costo: valor })));
        } else {
            tdCosto.classList.add("celda-calc");
            tdCosto.dataset.campo = "costo";
            tdCosto.textContent = insumo.costo_fmt;
            tdCosto.title = insumo.es_pct_mo
                ? "Total de mano de obra de la matriz (base del %)"
                : "Costo calculado (FSR, costo horario o composición)";
        }
        tr.appendChild(tdCosto);

        agregarCelda(tr, "col-num celda-calc", insumo.total_fmt, "total");

        const tdAcciones = document.createElement("td");
        tdAcciones.className = "col-acciones no-imprimir";
        const quitar = document.createElement("button");
        quitar.type = "button";
        quitar.className = "btn-quitar";
        quitar.textContent = "✕";
        quitar.title = "Quitar insumo de la matriz";
        quitar.addEventListener("click", async () => {
            if (!confirm("¿Quitar " + insumo.clave + " de la matriz?")) return;
            try {
                const json = await llamar(
                    "/api/matriz/" + encodeURIComponent(MATRIZ) + "/insumo/" +
                    encodeURIComponent(insumo.clave) + SUFIJO, "DELETE");
                pintar(json.ficha, true);
            } catch (err) { avisar(err.message, true); }
        });
        tdAcciones.appendChild(quitar);
        tr.appendChild(tdAcciones);
        return tr;
    }

    function construirFilaComponente(insumo, comp) {
        const tr = document.createElement("tr");
        tr.dataset.clave = insumo.clave + "/" + comp.clave;
        tr.dataset.tipo = insumo.tipo;
        tr.dataset.padre = insumo.clave;
        tr.className = "fila-componente";
        agregarCelda(tr, "col-tipo", "");
        const tdClave = document.createElement("td");
        tdClave.className = "col-clave celda-sangria";
        tdClave.innerHTML = "<code>" + comp.clave + "</code>";
        tr.appendChild(tdClave);
        agregarCelda(tr, "col-desc", comp.descripcion);
        agregarCelda(tr, "col-unidad", comp.unidad);
        agregarCelda(tr, "col-num", comp.cantidad);
        agregarCelda(tr, "col-num", comp.costo_fmt);
        agregarCelda(tr, "col-num", "");
        agregarCelda(tr, "col-acciones no-imprimir", "");
        return tr;
    }

    function agregarCelda(tr, clase, texto, campo) {
        const td = document.createElement("td");
        td.className = clase;
        td.textContent = texto || "";
        if (campo) td.dataset.campo = campo;
        tr.appendChild(td);
    }

    function crearEditable(valor, guardar) {
        const input = document.createElement("input");
        input.className = "celda-editable editable-numero";
        input.value = valor == null ? "" : valor;
        input.addEventListener("focus", () => { input.dataset.previo = input.value; });
        input.addEventListener("keydown", (ev) => {
            if (ev.key === "Escape") {
                input.value = input.dataset.previo || "";
                input.blur();
                ev.preventDefault();
            } else if (ev.key === "Enter") {
                ev.preventDefault();
                input.blur();
                enfocarSiguiente(input);
            }
        });
        input.addEventListener("change", async () => {
            if (input.value === input.dataset.previo) return;
            input.classList.add("pendiente");
            try {
                const json = await guardar(input.value);
                pintar(json.ficha, false);
                input.dataset.previo = input.value;
                avisar("");
            } catch (err) {
                input.value = input.dataset.previo || "";
                avisar(err.message, true);
            } finally {
                input.classList.remove("pendiente");
            }
        });
        return input;
    }

    function enfocarSiguiente(input) {
        const fila = input.closest("tr");
        const indice = Array.prototype.indexOf.call(
            fila.querySelectorAll("input"), input);
        let siguiente = fila.nextElementSibling;
        while (siguiente) {
            if (siguiente.style.display !== "none") {
                const inputs = siguiente.querySelectorAll("input.celda-editable");
                const destino = inputs[Math.min(indice, inputs.length - 1)];
                if (destino) { destino.focus(); destino.select(); return; }
            }
            siguiente = siguiente.nextElementSibling;
        }
    }

    /* Actualiza importes sin reconstruir filas (conserva el foco). */
    function actualizarCeldas() {
        const porClave = {};
        for (const insumo of ficha.insumos) porClave[insumo.clave] = insumo;
        for (const tr of cuerpo.querySelectorAll("tr.fila-insumo")) {
            const insumo = porClave[tr.dataset.clave];
            if (!insumo) continue;
            const tdCosto = tr.querySelector("td[data-campo='costo']");
            if (tdCosto) tdCosto.textContent = insumo.costo_fmt;
            const tdTotal = tr.querySelector("td[data-campo='total']");
            if (tdTotal) tdTotal.textContent = insumo.total_fmt;
        }
    }

    // ------------------------------------------------------------- alta
    document.getElementById("alta-boton").addEventListener("click", agregarInsumo);
    document.getElementById("alta-cantidad").addEventListener("keydown", (ev) => {
        if (ev.key === "Enter") { ev.preventDefault(); agregarInsumo(); }
    });

    async function agregarInsumo() {
        const recurso = document.getElementById("alta-recurso");
        const cantidad = document.getElementById("alta-cantidad");
        if (!recurso.value.trim()) { recurso.focus(); return; }
        try {
            const json = await llamar(
                "/api/matriz/" + encodeURIComponent(MATRIZ) + "/insumo" + SUFIJO,
                "POST", { recurso: recurso.value, cantidad: cantidad.value || "1" });
            pintar(json.ficha, true);
            recurso.value = "";
            cantidad.value = "1";
            recurso.focus();
            avisar("Insumo agregado.");
        } catch (err) { avisar(err.message, true); }
    }

    // -------------------------------------------------------------- pie
    function pintarPie(reconstruir) {
        document.getElementById("pie-factor").textContent = ficha.pie.factor;
        if (!reconstruir && cuerpoPie.children.length) {
            // Actualiza importes en sitio.
            for (const renglon of ficha.pie.renglones) {
                const tr = cuerpoPie.querySelector(
                    "tr[data-id='" + renglon.id + "']");
                if (!tr) continue;
                tr.querySelector("[data-campo='base']").textContent =
                    renglon.base_fmt;
                tr.querySelector("[data-campo='importe']").textContent =
                    renglon.importe_fmt;
            }
            actualizarExtremosPie();
            return;
        }
        cuerpoPie.innerHTML = "";

        const trCD = document.createElement("tr");
        trCD.className = "fila-cd";
        trCD.innerHTML = "<td>Costo directo</td><td></td><td></td><td></td>" +
            "<td class='col-num' data-extremo='cd'></td>";
        cuerpoPie.appendChild(trCD);

        for (const renglon of ficha.pie.renglones) {
            const tr = document.createElement("tr");
            tr.dataset.id = renglon.id;
            const tdNombre = document.createElement("td");
            tdNombre.textContent = "+ " + renglon.nombre;
            tr.appendChild(tdNombre);

            const tdPct = document.createElement("td");
            tdPct.className = "col-num";
            tdPct.appendChild(crearEditable(renglon.porcentaje, (valor) =>
                llamar("/api/pie/" + encodeURIComponent(renglon.id) + SUFIJO,
                    "PATCH", { porcentaje: valor })));
            tr.appendChild(tdPct);

            const tdBase = document.createElement("td");
            tdBase.className = "col-base";
            const select = document.createElement("select");
            select.className = "selector-base";
            for (const base of ["Acumulable", "Directo"]) {
                const opcion = document.createElement("option");
                opcion.value = base;
                opcion.textContent = base;
                opcion.selected = renglon.base === base;
                select.appendChild(opcion);
            }
            select.addEventListener("change", async () => {
                try {
                    const json = await llamar(
                        "/api/pie/" + encodeURIComponent(renglon.id) + SUFIJO,
                        "PATCH", { base: select.value });
                    pintar(json.ficha, false);
                } catch (err) { avisar(err.message, true); }
            });
            tdBase.appendChild(select);
            tr.appendChild(tdBase);

            const tdSobre = document.createElement("td");
            tdSobre.className = "col-num celda-calc";
            tdSobre.dataset.campo = "base";
            tdSobre.textContent = renglon.base_fmt;
            tr.appendChild(tdSobre);

            const tdImporte = document.createElement("td");
            tdImporte.className = "col-num celda-calc";
            tdImporte.dataset.campo = "importe";
            tdImporte.textContent = renglon.importe_fmt;
            tr.appendChild(tdImporte);
            cuerpoPie.appendChild(tr);
        }

        const trPV = document.createElement("tr");
        trPV.className = "fila-pv";
        trPV.innerHTML = "<td>PRECIO UNITARIO DE VENTA</td>" +
            "<td></td><td></td><td></td>" +
            "<td class='col-num' data-extremo='pv'></td>";
        cuerpoPie.appendChild(trPV);
        actualizarExtremosPie();
    }

    function actualizarExtremosPie() {
        const cd = cuerpoPie.querySelector("[data-extremo='cd']");
        if (cd) cd.textContent = ficha.pie.costo_directo_fmt;
        const pv = cuerpoPie.querySelector("[data-extremo='pv']");
        if (pv) pv.textContent = ficha.pie.precio_venta_fmt;
    }

    // Descripción de la matriz editable en el encabezado.
    const descripcion = document.getElementById("ficha-descripcion");
    descripcion.addEventListener("focus", () => {
        descripcion.dataset.previo = descripcion.value;
    });
    descripcion.addEventListener("change", async () => {
        try {
            const json = await llamar(
                "/api/recurso/" + encodeURIComponent(MATRIZ) + SUFIJO,
                "PATCH", { descripcion: descripcion.value });
            pintar(json.ficha, false);
        } catch (err) {
            descripcion.value = descripcion.dataset.previo || "";
            avisar(err.message, true);
        }
    });

    // ------------------------------------------------------------ inicio
    llamar("/api/matriz/" + encodeURIComponent(MATRIZ) +
        "?concepto=" + encodeURIComponent(CONCEPTO))
        .then((json) => pintar(json.ficha, true))
        .catch((err) => {
            cuerpo.innerHTML = "";
            avisar("No se pudo cargar la ficha: " + err.message, true);
        });
}());
