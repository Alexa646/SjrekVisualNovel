"""
motor.py — El "cerebro" de la novela visual.

Lee el guion (archivos .txt con una sintaxis sencilla) y lleva el estado
de la partida: en qué escena estás, qué variables tienes, qué fondo y qué
personajes se ven. No depende de pygame, así que puedes probar tu historia
en la terminal:

    python3 motor.py historia.txt --terminal    # jugar en modo texto
    python3 motor.py historia.txt --revisar     # buscar errores en el guion
"""
import json
import os
import re
import sys


class ErrorGuion(Exception):
    """Error en el guion, con archivo y número de línea para encontrarlo rápido."""


# Lo único que pueden usar las condiciones y operaciones del guion.
_CONSTANTES = {"verdadero": True, "falso": False, "True": True, "False": False,
               "min": min, "max": max, "abs": abs}
_GLOBALES = {"__builtins__": {}}


class _Variables(dict):
    """Diccionario de variables: una variable que no existe vale 0."""

    def __missing__(self, clave):
        return _CONSTANTES.get(clave, 0)


RE_TITULO = re.compile(r'^titulo\s+"([^"]+)"$')
RE_PERSONAJE = re.compile(r'^personaje\s+(\w+)\s+"([^"]+)"(?:\s+(#[0-9a-fA-F]{6}))?$')
RE_FONDO_DEF = re.compile(r'^fondo_def\s+(\w+)\s+(#[0-9a-fA-F]{6})(?:\s+(#[0-9a-fA-F]{6}))?$')
RE_OPCION = re.compile(r'^\*\s*(?:\(si\s+(.+?)\)\s*)?(.+?)\s*(?:->\s*(\w+))?\s*(?:\|\s*(.+))?$')
RE_ASIGNA = re.compile(r'^(\w+)\s*([+\-*]?=)\s*(.+)$')
RE_SI_SALTO = re.compile(r'^si\s+(.+?)\s*->\s*(\w+)$')
RE_SI_LINEA = re.compile(r'^si\s+([^:]+?)\s*:\s*(.+)$')
RE_FINAL = re.compile(r'^final\s+(\w+)\s+"([^"]+)"(?:\s+"([^"]*)")?$')
RE_DIALOGO = re.compile(r'^(\w+)\s*:\s*(.+)$')
RE_INTERPOLA = re.compile(r'\{(\w+)\}')

POSICIONES = {"izquierda": "izquierda", "izq": "izquierda", "centro": "centro",
              "derecha": "derecha", "der": "derecha"}


def _dividir_efectos(texto):
    """Separa 'a += 1, b = max(a, 2)' por comas que no estén entre paréntesis."""
    return [p.strip() for p in re.split(r',(?![^()]*\))', texto) if p.strip()]


def _quitar_comillas(texto):
    texto = texto.strip()
    if len(texto) >= 2 and texto[0] == texto[-1] and texto[0] in "\"'":
        return texto[1:-1]
    return texto


def _leer_lineas(ruta, pila=()):
    """Lee un archivo y expande las líneas 'incluir otro_archivo.txt'."""
    ruta = os.path.abspath(ruta)
    if ruta in pila:
        raise ErrorGuion(f"{os.path.basename(ruta)} se incluye a sí mismo")
    with open(ruta, encoding="utf-8") as f:
        crudas = f.read().splitlines()
    carpeta = os.path.dirname(ruta)
    for n, cruda in enumerate(crudas, 1):
        linea = cruda.strip()
        if linea.startswith("incluir "):
            otra = os.path.join(carpeta, linea[8:].strip())
            if not os.path.exists(otra):
                raise ErrorGuion(f"{os.path.basename(ruta)}, línea {n}: no existe el archivo {linea[8:].strip()}")
            yield from _leer_lineas(otra, pila + (ruta,))
        else:
            yield os.path.basename(ruta), n, linea


class Guion:
    """El guion ya interpretado: escenas, personajes, fondos y finales."""

    def __init__(self, lineas):
        self.titulo = "Mi novela visual"
        self.personajes = {}   # id -> {"nombre": ..., "color": ...}
        self.fondos = {}       # id -> (color_arriba, color_abajo)
        self.escenas = {}      # nombre -> lista de instrucciones
        self.orden = []        # escenas en el orden del archivo
        self.finales = {}      # id -> (titulo, descripcion)
        self._interpretar(lineas)
        self._comprobar_destinos()

    # ------------------------------------------------------------------ lectura
    def _interpretar(self, lineas):
        actual = None
        for archivo, n, linea in lineas:
            if not linea or linea.startswith("#"):
                continue
            donde = f"{archivo}, línea {n}"

            def error(msg):
                raise ErrorGuion(f"{donde}: {msg}\n    → {linea}")

            if linea.startswith("[") and linea.endswith("]"):
                actual = linea[1:-1].strip()
                if not re.fullmatch(r"\w+", actual):
                    error("el nombre de una escena solo puede tener letras, números y _")
                if actual in self.escenas:
                    error(f"la escena [{actual}] ya existe")
                self.escenas[actual] = []
                self.orden.append(actual)
                continue
            if (m := RE_TITULO.match(linea)):
                self.titulo = m[1]
                continue
            if (m := RE_PERSONAJE.match(linea)):
                self.personajes[m[1]] = {"nombre": m[2], "color": m[3] or "#ffffff"}
                continue
            if (m := RE_FONDO_DEF.match(linea)):
                self.fondos[m[1]] = (m[2], m[3] or m[2])
                continue
            if actual is None:
                error("esta línea tiene que ir dentro de una escena, por ejemplo [inicio]")

            cmds = self.escenas[actual]
            if linea.startswith("*"):
                if not cmds or cmds[-1]["op"] != "menu":
                    cmds.append({"op": "menu", "texto": "", "opciones": [], "linea": n, "donde": donde})
                cmds[-1]["opciones"].append(self._opcion(linea, error, donde))
            else:
                cmds.extend(self._instruccion(linea, error, n, donde))

        if not self.orden:
            raise ErrorGuion("el guion no tiene ninguna escena")

    def _expresion(self, expr, error):
        try:
            compile(expr, "<guion>", "eval")
        except SyntaxError:
            error(f"no entiendo la expresión «{expr}»")
        return expr

    def _asignacion(self, texto, error):
        m = RE_ASIGNA.match(texto)
        if not m:
            error(f"no entiendo la operación «{texto}» (ejemplo: valor += 1)")
        return (m[1], m[2], self._expresion(m[3], error))

    def _opcion(self, linea, error, donde):
        m = RE_OPCION.match(linea)
        if not m:
            error("una opción se escribe así:  * Texto de la opción -> escena | efectos")
        return {"cond": self._expresion(m[1], error) if m[1] else None,
                "texto": m[2].strip(), "destino": m[3],
                "efectos": [self._asignacion(e, error) for e in _dividir_efectos(m[4] or "")],
                "donde": donde}

    def _instruccion(self, linea, error, n, donde):
        """Convierte una línea en una lista de instrucciones."""
        def c(op, **datos):
            datos.update(op=op, linea=n, donde=donde)
            return [datos]

        if linea.startswith("? "):
            return c("menu", texto=linea[2:].strip(), opciones=[])
        if linea.startswith("$"):
            return [x for parte in _dividir_efectos(linea[1:])
                    for x in c("asigna", efecto=self._asignacion(parte, error))]
        if linea.startswith("si "):
            if (m := RE_SI_SALTO.match(linea)):
                return c("si", cond=self._expresion(m[1], error), destino=m[2])
            if (m := RE_SI_LINEA.match(linea)):
                resto = m[2].strip()
                if resto.startswith(("?", "*", "si ")):
                    error("después de 'si condición:' va una sola línea normal")
                return c("si_linea", cond=self._expresion(m[1], error),
                         cmds=self._instruccion(resto, error, n, donde))
            error("se escribe  si condición -> escena   o   si condición: línea")
        if linea.startswith("ir "):
            return c("ir", destino=linea[3:].strip())
        if linea.startswith("fondo "):
            return c("fondo", id=linea[6:].strip())
        if linea.startswith("mostrar "):
            partes = linea.split()
            pos = POSICIONES.get(partes[2] if len(partes) > 2 else "centro")
            if pos is None:
                error("la posición puede ser izquierda, centro o derecha")
            if partes[1] not in self.personajes:
                error(f"el personaje «{partes[1]}» no está definido")
            return c("mostrar", id=partes[1], pos=pos)
        if linea.startswith("ocultar "):
            return c("ocultar", id=linea[8:].strip())
        if linea.startswith("final "):
            m = RE_FINAL.match(linea)
            if not m:
                error('un final se escribe así:  final id "Título" "Descripción opcional"')
            self.finales[m[1]] = (m[2], m[3] or "")
            return c("final", id=m[1])
        m = RE_DIALOGO.match(linea)
        if m and m[1] in self.personajes:
            return c("decir", quien=m[1], texto=_quitar_comillas(m[2]))
        return c("decir", quien=None, texto=_quitar_comillas(linea))

    def _destinos(self, cmd):
        if cmd["op"] in ("si", "ir"):
            return [cmd["destino"]]
        if cmd["op"] == "menu":
            return [o["destino"] for o in cmd["opciones"] if o["destino"]]
        if cmd["op"] == "si_linea":
            return [d for sub in cmd["cmds"] for d in self._destinos(sub)]
        return []

    def _comprobar_destinos(self):
        for nombre in self.orden:
            for cmd in self.escenas[nombre]:
                for d in self._destinos(cmd):
                    if d not in self.escenas:
                        raise ErrorGuion(f"{cmd['donde']}: la escena [{d}] no existe")

    # ---------------------------------------------------------------- revisión
    def contar_decisiones(self):
        return sum(1 for e in self.orden for c in self.escenas[e] if c["op"] == "menu")

    def revisar(self):
        """Devuelve una lista de avisos: escenas inalcanzables, finales perdidos…"""
        grafo = {}
        for i, nombre in enumerate(self.orden):
            destinos, sigue = set(), True
            for c in self.escenas[nombre]:
                destinos.update(self._destinos(c))
                if c["op"] in ("ir", "final"):
                    sigue = False
                    break
                if c["op"] == "menu" and all(o["destino"] for o in c["opciones"]):
                    sigue = False
                    break
            if sigue and i + 1 < len(self.orden):
                destinos.add(self.orden[i + 1])
            grafo[nombre] = destinos

        alcanzables, pendientes = set(), [self.orden[0]]
        while pendientes:
            e = pendientes.pop()
            if e not in alcanzables:
                alcanzables.add(e)
                pendientes.extend(grafo[e])

        avisos = [f"La escena [{e}] nunca se alcanza" for e in self.orden if e not in alcanzables]
        for e in self.orden:
            for c in self.escenas[e]:
                if c["op"] == "decir" and c["texto"].startswith(("si ", "ir ", "* ", "$")):
                    avisos.append(f"{c['donde']}: parece una instrucción mal escrita: «{c['texto']}»")
                if c["op"] == "menu" and len(c["opciones"]) < 2:
                    avisos.append(f"{c['donde']}: este menú tiene menos de 2 opciones")
        return avisos


def cargar_guion(ruta):
    return Guion(_leer_lineas(ruta))


class Partida:
    """El estado de una partida. La interfaz llama a siguiente() y elegir()."""

    def __init__(self, guion):
        self.g = guion
        self.reiniciar()

    def reiniciar(self):
        self.escena = self.g.orden[0]
        self.pc = 0                    # instrucción actual dentro de la escena
        self.marca = (self.escena, 0)  # instrucción que se está mostrando (para guardar)
        self.vars = _Variables()
        self.fondo = None
        self.visibles = {}             # id de personaje -> posición
        self.historial = []            # (nombre, texto) de lo que ya se dijo
        self._menu = None

    # ------------------------------------------------------------- utilidades
    def evaluar(self, expr):
        try:
            return eval(expr, _GLOBALES, self.vars)
        except Exception as e:
            raise ErrorGuion(f"error al calcular «{expr}» en [{self.escena}]: {e}") from None

    def texto(self, t):
        return RE_INTERPOLA.sub(lambda m: str(self.vars[m[1]]), t)

    def _asignar(self, efecto):
        var, op, expr = efecto
        valor = self.evaluar(expr)
        if op == "=":
            self.vars[var] = valor
        elif op == "+=":
            self.vars[var] = self.vars[var] + valor
        elif op == "-=":
            self.vars[var] = self.vars[var] - valor
        elif op == "*=":
            self.vars[var] = self.vars[var] * valor

    def _saltar(self, destino):
        self.escena, self.pc = destino, 0

    def _ejecutar(self, c):
        """Ejecuta una instrucción. Devuelve un evento si hay algo que mostrar."""
        op = c["op"]
        if op == "fondo":
            self.fondo = c["id"]
        elif op == "mostrar":
            self.visibles[c["id"]] = c["pos"]
        elif op == "ocultar":
            if c["id"] == "todos":
                self.visibles.clear()
            else:
                self.visibles.pop(c["id"], None)
        elif op == "asigna":
            self._asignar(c["efecto"])
        elif op == "si":
            if self.evaluar(c["cond"]):
                self._saltar(c["destino"])
        elif op == "si_linea":
            if self.evaluar(c["cond"]):
                for sub in c["cmds"]:
                    ev = self._ejecutar(sub)
                    if ev:
                        return ev
        elif op == "ir":
            self._saltar(c["destino"])
        elif op == "decir":
            quien = c["quien"]
            p = self.g.personajes.get(quien, {})
            texto = self.texto(c["texto"])
            self.historial.append((p.get("nombre", ""), texto))
            return {"tipo": "decir", "quien": quien, "nombre": p.get("nombre", ""),
                    "color": p.get("color", "#ffffff"), "texto": texto}
        elif op == "menu":
            visibles = [(i, self.texto(o["texto"])) for i, o in enumerate(c["opciones"])
                        if not o["cond"] or self.evaluar(o["cond"])]
            if not visibles:
                raise ErrorGuion(f"{c['donde']}: ninguna opción del menú está disponible")
            self._menu = c
            return {"tipo": "elegir", "texto": self.texto(c["texto"]), "opciones": visibles}
        elif op == "final":
            titulo, desc = self.g.finales[c["id"]]
            return {"tipo": "final", "id": c["id"], "titulo": titulo, "descripcion": desc}
        return None

    # ----------------------------------------------------------------- avance
    def siguiente(self):
        """Ejecuta instrucciones hasta llegar a algo que mostrar.

        Devuelve un diccionario con "tipo":
          "decir"     -> quien, nombre, color, texto
          "elegir"    -> texto, opciones [(indice, texto), ...]
          "final"     -> id, titulo, descripcion
          "fin_guion" -> se acabó el archivo sin un 'final'
        """
        for _ in range(100_000):
            cmds = self.g.escenas[self.escena]
            if self.pc >= len(cmds):  # escena terminada: pasa a la siguiente del archivo
                i = self.g.orden.index(self.escena)
                if i + 1 >= len(self.g.orden):
                    return {"tipo": "fin_guion"}
                self._saltar(self.g.orden[i + 1])
                continue
            c = cmds[self.pc]
            self.marca = (self.escena, self.pc)
            self.pc += 1
            ev = self._ejecutar(c)
            if ev:
                return ev
        raise ErrorGuion("bucle infinito: revisa tus 'ir' y 'si'")

    def elegir(self, indice):
        """Aplica la opción 'indice' del menú actual.

        La variable 'eleccion' guarda el número de la opción (1, 2, 3...) para
        poder reaccionar con  si eleccion == 2: ...  justo después del menú.
        """
        opcion = self._menu["opciones"][indice]
        self.historial.append(("➜", self.texto(opcion["texto"])))
        self.vars["eleccion"] = indice + 1
        for efecto in opcion["efectos"]:
            self._asignar(efecto)
        if opcion["destino"]:
            self._saltar(opcion["destino"])
        # sin destino: la historia sigue en la línea de abajo del menú
        self.marca = (self.escena, self.pc)
        self._menu = None

    # ------------------------------------------------------- guardar / cargar
    def a_diccionario(self):
        return {"escena": self.marca[0], "pc": self.marca[1], "vars": dict(self.vars),
                "fondo": self.fondo, "visibles": self.visibles,
                "historial": self.historial[-200:]}

    def desde_diccionario(self, datos):
        if datos["escena"] not in self.g.escenas:
            raise ErrorGuion("la partida guardada es de otra versión del guion")
        self.escena, self.pc = datos["escena"], datos["pc"]
        self.vars = _Variables(datos["vars"])
        self.fondo = datos["fondo"]
        self.visibles = dict(datos["visibles"])
        self.historial = [tuple(h) for h in datos.get("historial", [])]
        if self.historial:  # el último texto se volverá a mostrar con siguiente()
            self.historial.pop()


class Finales:
    """Recuerda qué finales has descubierto entre partidas."""

    def __init__(self, ruta):
        self.ruta = ruta
        try:
            with open(ruta, encoding="utf-8") as f:
                self.vistos = set(json.load(f))
        except (OSError, ValueError):
            self.vistos = set()

    def agregar(self, id_final):
        if id_final not in self.vistos:
            self.vistos.add(id_final)
            with open(self.ruta, "w", encoding="utf-8") as f:
                json.dump(sorted(self.vistos), f, ensure_ascii=False)


# ------------------------------------------------------------- modo terminal
def jugar_en_terminal(guion):
    partida = Partida(guion)
    print(f"\n=== {guion.titulo} ===  (Enter para avanzar, Ctrl+C para salir)\n")
    while True:
        ev = partida.siguiente()
        if ev["tipo"] == "decir":
            prefijo = f"{ev['nombre']}: " if ev["nombre"] else ""
            input(f"{prefijo}{ev['texto']}")
        elif ev["tipo"] == "elegir":
            if ev["texto"]:
                print(f"\n{ev['texto']}")
            for n, (_, texto) in enumerate(ev["opciones"], 1):
                print(f"  {n}) {texto}")
            while True:
                r = input("> ").strip()
                if r.isdigit() and 1 <= int(r) <= len(ev["opciones"]):
                    break
            partida.elegir(ev["opciones"][int(r) - 1][0])
            print()
        else:
            if ev["tipo"] == "final":
                print(f"\n*** FINAL: {ev['titulo']} ***\n{ev['descripcion']}")
            print(f"\nVariables: {dict(partida.vars)}")
            return


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    try:
        g = cargar_guion(sys.argv[1])
    except (ErrorGuion, OSError) as e:
        print(f"Error en el guion:\n{e}")
        sys.exit(1)
    if "--revisar" in sys.argv:
        print(f"«{g.titulo}»: {len(g.orden)} escenas, {g.contar_decisiones()} decisiones, "
              f"{len(g.personajes)} personajes, {len(g.finales)} finales")
        for id_f, (t, _) in g.finales.items():
            print(f"  · {id_f}: {t}")
        avisos = g.revisar()
        print("\n".join(f"⚠ {a}" for a in avisos) if avisos else "✔ Sin problemas.")
    else:
        try:
            jugar_en_terminal(g)
        except (KeyboardInterrupt, EOFError):
            print("\nHasta luego.")
