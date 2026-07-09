/* Explosión de insumos + programa de suministros.
 *
 * El panel de configuración arma la consulta a /api/insumos; cada cambio
 * repinta la grilla completa (la explosión es de solo lectura). El
 * buscador y la numeración de periodos se resuelven en el cliente. */
(function () {
    "use strict";

    const flash = document.getElementById("flash-js");
    const cabeza = document.getElementById("cabeza-explosion");
    const cuerpo = document.getElementById("cuerpo-explosion");
    const pieTabla = document.getElementById("pie-explosion");
    const nota = document.getElementById("nota-grilla");

    const chkPrograma = document.getElementById("chk-programa");
    const configPrograma = document.getElementById("config-programa");
    const chkNumerados = document.getElementById("chk-numerados");
    const txtPrefijo = document.getElementById("txt-prefijo");
    const txtBuscar = document.getElementById("txt-buscar");

    let datos = null;

    function avisar(mensaje, esError) {
        flash.innerHTML = "";
        if (!mensaje) return;
        const p = document.createElement("p");
        p.className = "flash " + (esError ? "flash-error" : "flash-ok");
        p.textContent = mensaje;
        flash.appendChild(p);
        setTimeout(() => { if (p.parentNode) p.remove(); }, 6000);
    }

    // ------------------------------------------------------- consulta
    function parametros() {
        const nivel = document.querySelector("input[name='nivel']:checked").value;
        const marcados = Array.from(
            document.querySelectorAll(".filtro-tipo:checked"),
            (c) => c.value);
        const todos = document.querySelectorAll(".filtro-tipo").length;
        const query = new URLSearchParams({ nivel: nivel });
        if (marcados.length && marcados.length < todos) {
            query.set("tipos", marcados.join(","));
        } else if (!marcados.length) {
            query.set("tipos", "∅");   // nada marcado: conjunto vacío
        }
        if (document.getElementById("chk-desglosar").checked) {
            query.set("desglosar", "1");
        }
        if (chkPrograma && chkPrograma.checked) {
            query.set("programa", "1");
            query.set("escala", document.getElementById("sel-escala").value);
            query.set("por", document.getElementById("sel-por").value);
        }
        return query;
    }

    async function cargar() {
        const query = parametros();
        if (query.get("tipos") === "∅") {
            datos = { filas: [], periodos: [], totales_periodo: [],
                      total_importe_fmt: "0.00", num_insumos: 0 };
            pintar();
            return;
        }
        cuerpo.innerHTML = "<tr><td class='cargando'>Calculando…</td></tr>";
        try {
            const respuesta = await fetch("/api/insumos?" + query.toString());
            const json = await respuesta.json().catch(() => ({}));
            if (!respuesta.ok || json.ok === false) {
                throw new Error(json.error || ("Error " + respuesta.status));
            }
            datos = json.insumos;
            pintar();
        } catch (err) {
            cuerpo.innerHTML = "";
            avisar("No se pudo calcular la explosión: " + err.message, true);
        }
    }

    // -------------------------------------------------------- pintado
    function etiquetasPeriodo() {
        if (!datos.periodos.length) return [];
        if (chkNumerados && chkNumerados.checked) {
            const prefijo = (txtPrefijo.value || "P").trim() || "P";
            return datos.periodos.map((p, i) => ({
                texto: prefijo + (i + 1), titulo: p,
            }));
        }
        return datos.periodos.map((p) => ({ texto: p, titulo: "" }));
    }

    function pintar() {
        document.getElementById("chip-insumos").textContent = datos.num_insumos;
        document.getElementById("chip-total").textContent =
            "$ " + datos.total_importe_fmt;

        const periodos = etiquetasPeriodo();
        const trCabeza = document.createElement("tr");
        for (const titulo of ["Tipo", "Clave", "Descripción", "Unidad",
                              "Cantidad", "Costo unitario", "Importe $",
                              "% Part."]) {
            const th = document.createElement("th");
            th.textContent = titulo;
            th.className = ["Cantidad", "Costo unitario", "Importe $",
                            "% Part."].includes(titulo)
                ? "col-num" : "";
            trCabeza.appendChild(th);
        }
        for (const periodo of periodos) {
            const th = document.createElement("th");
            th.className = "col-num col-periodo";
            th.textContent = periodo.texto;
            if (periodo.titulo) th.title = periodo.titulo;
            trCabeza.appendChild(th);
        }
        cabeza.innerHTML = "";
        cabeza.appendChild(trCabeza);

        cuerpo.innerHTML = "";
        for (const fila of datos.filas) {
            const tr = document.createElement("tr");
            tr.dataset.busqueda =
                (fila.clave + " " + fila.descripcion).toLowerCase();

            const tdTipo = document.createElement("td");
            tdTipo.className = "col-tipo";
            const badge = document.createElement("span");
            badge.className = "badge badge-" +
                fila.tipo.toLowerCase().replace(/[^a-z]/g, "");
            badge.textContent = fila.tipo;
            tdTipo.appendChild(badge);
            tr.appendChild(tdTipo);

            const tdClave = document.createElement("td");
            tdClave.className = "col-clave";
            tdClave.innerHTML = "<code></code>";
            tdClave.firstChild.textContent = fila.clave;
            tr.appendChild(tdClave);

            celda(tr, "col-desc", fila.descripcion);
            celda(tr, "col-unidad", fila.unidad);
            celda(tr, "col-num", fila.cantidad_fmt);
            celda(tr, "col-num", fila.costo_fmt);
            celda(tr, "col-num celda-calc", fila.importe_fmt);
            celda(tr, "col-pct", fila.pct + " %");
            for (const valor of fila.periodos || []) {
                celda(tr, "col-num col-periodo celda-calc", valor);
            }
            cuerpo.appendChild(tr);
        }
        if (!datos.filas.length) {
            cuerpo.innerHTML = "<tr><td colspan='8' class='cargando'>" +
                "Sin insumos con la configuración elegida.</td></tr>";
        }

        pieTabla.innerHTML = "";
        if (datos.filas.length) {
            const tr = document.createElement("tr");
            tr.className = "fila-total";
            celda(tr, "", "");
            celda(tr, "", "");
            celda(tr, "col-desc", "TOTAL");
            celda(tr, "", "");
            celda(tr, "", "");
            celda(tr, "", "");
            celda(tr, "col-num", datos.total_importe_fmt);
            celda(tr, "col-pct", "100.00 %");
            for (const total of datos.totales_periodo) {
                celda(tr, "col-num col-periodo", total);
            }
            pieTabla.appendChild(tr);
        }
        aplicarBusqueda();
    }

    function celda(tr, clase, texto) {
        const td = document.createElement("td");
        td.className = clase;
        td.textContent = texto || "";
        tr.appendChild(td);
    }

    // ------------------------------------------------------- buscador
    function aplicarBusqueda() {
        const termino = txtBuscar.value.trim().toLowerCase();
        let visibles = 0;
        for (const tr of cuerpo.querySelectorAll("tr[data-busqueda]")) {
            const visible = !termino || tr.dataset.busqueda.includes(termino);
            tr.style.display = visible ? "" : "none";
            if (visible) visibles += 1;
        }
        nota.textContent = termino
            ? visibles + " de " + datos.filas.length + " insumos"
            : "";
    }

    // ------------------------------------------------------------ CSV
    function descargarCSV() {
        if (!datos || !datos.filas.length) return;
        const periodos = etiquetasPeriodo();
        const escapar = (v) => '"' + String(v == null ? "" : v)
            .replace(/"/g, '""') + '"';
        const filas = [["Tipo", "Clave", "Descripción", "Unidad", "Cantidad",
                        "Costo unitario", "Importe", "% Part."]
            .concat(periodos.map((p) => p.titulo || p.texto))];
        for (const fila of datos.filas) {
            filas.push([fila.tipo, fila.clave, fila.descripcion, fila.unidad,
                        fila.cantidad_fmt, fila.costo_fmt, fila.importe_fmt,
                        fila.pct].concat(fila.periodos || []));
        }
        filas.push(["", "", "TOTAL", "", "", "", datos.total_importe_fmt,
                    "100.00"].concat(datos.totales_periodo));
        const csv = filas.map((f) => f.map(escapar).join(",")).join("\r\n");
        const enlace = document.createElement("a");
        enlace.href = URL.createObjectURL(
            new Blob(["﻿" + csv], { type: "text/csv;charset=utf-8" }));
        enlace.download = "explosion_insumos.csv";
        enlace.click();
        URL.revokeObjectURL(enlace.href);
    }

    // --------------------------------------------------------- eventos
    for (const control of document.querySelectorAll(
            "input[name='nivel'], .filtro-tipo, #chk-desglosar")) {
        control.addEventListener("change", cargar);
    }
    if (chkPrograma) {
        chkPrograma.addEventListener("change", () => {
            configPrograma.hidden = !chkPrograma.checked;
            cargar();
        });
        document.getElementById("sel-escala")
            .addEventListener("change", cargar);
        document.getElementById("sel-por")
            .addEventListener("change", cargar);
        chkNumerados.addEventListener("change", () => { if (datos) pintar(); });
        txtPrefijo.addEventListener("input", () => {
            if (datos && chkNumerados.checked) pintar();
        });
    }
    txtBuscar.addEventListener("input", aplicarBusqueda);
    document.getElementById("btn-csv").addEventListener("click", descargarCSV);

    cargar();
}());
