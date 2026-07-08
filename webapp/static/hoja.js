/* Hoja de presupuesto: tree-grid con edición en celda + Gantt alineado.
 *
 * Estado en el cliente:
 *  - filas: último payload de /api/hoja (fuente de verdad tras cada PATCH)
 *  - colapsados: Set de ids de agrupadores cerrados (persiste entre repintados)
 *  - gantt: payload de /api/gantt (barras por id de fila)
 */
(function () {
    "use strict";

    const cuerpo = document.getElementById("cuerpo-hoja");
    const ganttCuerpo = document.getElementById("gantt-cuerpo");
    const ganttEncabezado = document.getElementById("gantt-encabezado");
    const panelGrid = document.getElementById("panel-grid");
    const panelGantt = document.getElementById("panel-gantt");
    const ganttScroll = document.getElementById("gantt-scroll");
    const flash = document.getElementById("flash-js");

    let filas = [];
    let padres = {};          // id -> id del padre
    let tienenHijos = new Set();
    let colapsados = new Set();
    let gantt = null;

    // ---------------------------------------------------------------- util
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

    // ------------------------------------------------------ construcción
    function indexar(datos) {
        filas = datos.filas;
        padres = {};
        tienenHijos = new Set();
        for (const f of filas) {
            padres[f.id] = f.padre;
            if (f.padre) tienenHijos.add(f.padre);
        }
    }

    function visible(id) {
        let padre = padres[id];
        while (padre) {
            if (colapsados.has(padre)) return false;
            padre = padres[padre];
        }
        return true;
    }

    function construirFila(f) {
        const tr = document.createElement("tr");
        tr.dataset.id = f.id;
        tr.dataset.tipo = f.tipo;
        tr.className = f.tipo === "agrupador"
            ? "fila-agrupador nivel-" + Math.min(f.nivel, 4) : "fila-concepto";

        // Clave (con sangría y flecha de expandir)
        const tdClave = document.createElement("td");
        tdClave.className = "col-clave";
        tdClave.style.paddingLeft = (0.4 + (f.nivel - 1) * 1.1) + "rem";
        if (f.tipo === "agrupador" && tienenHijos.has(f.id)) {
            const flecha = document.createElement("span");
            flecha.className = "flecha";
            flecha.textContent = colapsados.has(f.id) ? "▸" : "▾";
            flecha.addEventListener("click", () => alternar(f.id));
            tdClave.appendChild(flecha);
        }
        if (f.tipo === "concepto" && f.matriz) {
            const enlace = document.createElement("a");
            enlace.href = "/matriz/" + encodeURIComponent(f.matriz) +
                "?concepto=" + encodeURIComponent(f.clave);
            enlace.textContent = f.clave;
            enlace.title = "Abrir ficha de costeo (" + f.matriz + ")";
            tdClave.appendChild(enlace);
        } else {
            const texto = document.createElement("span");
            texto.textContent = f.clave;
            tdClave.appendChild(texto);
        }
        tr.appendChild(tdClave);

        // Descripción editable
        const tdDesc = document.createElement("td");
        tdDesc.className = "col-desc";
        tdDesc.appendChild(crearEditable(f, "descripcion", f.descripcion, "texto"));
        tr.appendChild(tdDesc);

        agregarCelda(tr, "col-unidad", f.unidad);

        // Cantidad editable (solo conceptos sin generador)
        const tdCant = document.createElement("td");
        tdCant.className = "col-num";
        if (f.tipo === "concepto") {
            const input = crearEditable(f, "cantidad", f.cantidad, "numero");
            if (f.tiene_generador) {
                input.disabled = true;
                input.title = "Cantidad calculada por números generadores " +
                    "(edítala en el wizard, paso 4).";
            }
            tdCant.appendChild(input);
        }
        tr.appendChild(tdCant);

        agregarCelda(tr, "col-num celda-calc", f.pu_fmt, "pu");
        agregarCelda(tr, "col-num celda-calc", f.importe_fmt, "importe");
        agregarCelda(tr, "col-pct celda-calc", f.pct, "pct");
        return tr;
    }

    function agregarCelda(tr, clase, texto, campo) {
        const td = document.createElement("td");
        td.className = clase;
        td.textContent = texto || "";
        if (campo) td.dataset.campo = campo;
        tr.appendChild(td);
    }

    function crearEditable(f, campo, valor, tipoDato) {
        const input = document.createElement("input");
        input.className = "celda-editable " +
            (tipoDato === "numero" ? "editable-numero" : "editable-texto");
        input.value = valor == null ? "" : valor;
        input.dataset.campo = campo;
        input.addEventListener("focus", () => { input.dataset.previo = input.value; });
        input.addEventListener("keydown", (ev) => manejarTeclas(ev, input, campo));
        input.addEventListener("change", () => confirmarEdicion(f, campo, input));
        return input;
    }

    function manejarTeclas(ev, input, campo) {
        if (ev.key === "Escape") {
            input.value = input.dataset.previo || "";
            input.blur();
            ev.preventDefault();
        } else if (ev.key === "Enter") {
            ev.preventDefault();
            input.blur();  // dispara change → PATCH
            enfocarSiguiente(input, campo);
        }
    }

    function enfocarSiguiente(input, campo) {
        const fila = input.closest("tr");
        let siguiente = fila.nextElementSibling;
        while (siguiente) {
            if (siguiente.style.display !== "none") {
                const destino = siguiente.querySelector(
                    "input[data-campo='" + campo + "']:not(:disabled)");
                if (destino) { destino.focus(); destino.select(); return; }
            }
            siguiente = siguiente.nextElementSibling;
        }
    }

    async function confirmarEdicion(f, campo, input) {
        if (input.value === input.dataset.previo) return;
        const datos = {}; datos[campo] = input.value;
        input.classList.add("pendiente");
        try {
            let json;
            if (f.tipo === "concepto") {
                json = await llamar("/api/concepto/" + encodeURIComponent(f.clave),
                    "PATCH", datos);
            } else {
                datos.ruta = f.ruta;
                json = await llamar("/api/agrupador", "PATCH", datos);
            }
            aplicarHoja(json.hoja, false);
            avisar("");
        } catch (err) {
            input.value = input.dataset.previo || "";
            avisar(err.message, true);
        } finally {
            input.classList.remove("pendiente");
        }
    }

    // ------------------------------------------------------- (re)pintado
    function pintarTodo() {
        cuerpo.innerHTML = "";
        for (const f of filas) {
            const tr = construirFila(f);
            if (!visible(f.id)) tr.style.display = "none";
            cuerpo.appendChild(tr);
        }
        pintarGantt();
    }

    /* Tras un PATCH: actualiza celdas calculadas en sitio, sin
     * reconstruir el DOM (conserva el foco y el flujo Tab/Enter). */
    function aplicarHoja(hoja, reconstruir) {
        indexar(hoja);
        for (const [campo, valor] of Object.entries(hoja.resumen)) {
            const chip = document.querySelector("[data-resumen='" + campo + "']");
            if (chip) chip.textContent = "$ " + valor;
        }
        if (reconstruir) { pintarTodo(); return; }
        const porId = {};
        for (const f of filas) porId[f.id] = f;
        for (const tr of cuerpo.querySelectorAll("tr[data-id]")) {
            const f = porId[tr.dataset.id];
            if (!f) continue;   // fila eliminada: pide recarga completa
            asignar(tr, "pu", f.pu_fmt);
            asignar(tr, "importe", f.importe_fmt);
            asignar(tr, "pct", f.pct);
        }
    }

    function asignar(tr, campo, valor) {
        const td = tr.querySelector("td[data-campo='" + campo + "']");
        if (td) td.textContent = valor || "";
    }

    // ------------------------------------------------- expandir/colapsar
    function alternar(id) {
        if (colapsados.has(id)) colapsados.delete(id);
        else colapsados.add(id);
        aplicarVisibilidad();
    }

    function aplicarVisibilidad() {
        const porId = {};
        for (const f of filas) porId[f.id] = f;
        for (const tr of cuerpo.querySelectorAll("tr[data-id]")) {
            const f = porId[tr.dataset.id];
            tr.style.display = visible(f.id) ? "" : "none";
            const flecha = tr.querySelector(".flecha");
            if (flecha) flecha.textContent = colapsados.has(f.id) ? "▸" : "▾";
        }
        pintarGantt();
    }

    document.querySelectorAll(".btn-nivel").forEach((btn) => {
        btn.addEventListener("click", () => {
            const nivel = parseInt(btn.dataset.nivel, 10);
            colapsados = new Set();
            if (nivel > 0) {
                for (const f of filas) {
                    if (f.tipo === "agrupador" && f.nivel >= nivel) {
                        colapsados.add(f.id);
                    }
                }
            }
            aplicarVisibilidad();
        });
    });

    // -------------------------------------------------------------- gantt
    function pintarGantt() {
        if (!gantt) {
            panelGantt.classList.add("gantt-vacio");
            ganttEncabezado.innerHTML = "";
            ganttCuerpo.innerHTML =
                "<p class='nota nota-gantt'>Sin actividades programadas. " +
                "Captura el programa en el wizard (paso 5) para ver las " +
                "barras aquí.</p>";
            return;
        }
        panelGantt.classList.remove("gantt-vacio");
        const ancho = gantt.ancho_px;
        const porDia = ancho / gantt.total_dias;

        ganttEncabezado.innerHTML = "";
        ganttEncabezado.style.width = ancho + "px";
        for (const mes of gantt.meses) {
            const div = document.createElement("div");
            div.className = "gantt-mes";
            div.style.left = (mes.off * porDia) + "px";
            div.style.width = (mes.dias * porDia) + "px";
            div.textContent = mes.etiqueta;
            ganttEncabezado.appendChild(div);
        }

        ganttCuerpo.innerHTML = "";
        ganttCuerpo.style.width = ancho + "px";
        for (const tr of cuerpo.querySelectorAll("tr[data-id]")) {
            if (tr.style.display === "none") continue;
            const filaDiv = document.createElement("div");
            filaDiv.className = "gantt-fila" +
                (tr.dataset.tipo === "agrupador" ? " gantt-fila-agrupador" : "");
            const barras = gantt.barras[tr.dataset.id] || [];
            for (const barra of barras) {
                const div = document.createElement("div");
                div.className = "gantt-barra" +
                    (barra.critica ? " critica" : "") +
                    (barra.resumen ? " resumen" : "");
                div.style.left = (barra.off * porDia) + "px";
                div.style.width = Math.max(3, barra.dias * porDia) + "px";
                div.title = barra.titulo;
                filaDiv.appendChild(div);
            }
            ganttCuerpo.appendChild(filaDiv);
        }
    }

    // Sincroniza scroll vertical entre la tabla y el gantt.
    let sincronizando = false;
    function sincronizar(origen, destino) {
        origen.addEventListener("scroll", () => {
            if (sincronizando) { sincronizando = false; return; }
            sincronizando = true;
            destino.scrollTop = origen.scrollTop;
        });
    }
    sincronizar(panelGrid, ganttScroll);
    sincronizar(ganttScroll, panelGrid);

    // Mostrar/ocultar panel del programa.
    document.getElementById("btn-gantt").addEventListener("click", () => {
        document.getElementById("hoja-layout").classList.toggle("sin-gantt");
    });

    // ----------------------------------------------------------- splitter
    const splitter = document.getElementById("splitter");
    splitter.addEventListener("mousedown", (ev) => {
        ev.preventDefault();
        const layout = document.getElementById("hoja-layout");
        const inicioX = ev.clientX;
        const anchoInicial = panelGrid.getBoundingClientRect().width;
        function mover(evM) {
            const nuevo = Math.max(360, anchoInicial + evM.clientX - inicioX);
            panelGrid.style.flex = "0 0 " + nuevo + "px";
        }
        function soltar() {
            document.removeEventListener("mousemove", mover);
            document.removeEventListener("mouseup", soltar);
        }
        document.addEventListener("mousemove", mover);
        document.addEventListener("mouseup", soltar);
    });

    // ------------------------------------------------------------- inicio
    Promise.all([llamar("/api/hoja"), llamar("/api/gantt")])
        .then(([rHoja, rGantt]) => {
            gantt = rGantt.gantt;
            indexar(rHoja.hoja);
            aplicarHoja(rHoja.hoja, true);
            if (!gantt) {
                document.getElementById("hoja-layout").classList.add("sin-gantt");
            }
        })
        .catch((err) => {
            cuerpo.innerHTML = "";
            avisar("No se pudo cargar el presupuesto: " + err.message, true);
        });
}());
