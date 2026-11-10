"""
juego.py — La parte visual de la novela (pygame).

    python juego.py                  # usa historia.txt
    python juego.py otra_historia.txt

Controles:
    Clic / Espacio / Enter   avanzar el texto
    1-9                      elegir una opción
    Ctrl (mantener)          adelantar rápido
    H o rueda del ratón      ver historial
    F5 / F9                  guardar / cargar
    Esc                      volver al menú
"""
import json
import math
import os
import sys

import pygame

from motor import ErrorGuion, Finales, Partida, cargar_guion

ANCHO, ALTO = 1280, 720
FPS = 60
VELOCIDAD_TEXTO = 45          # letras por segundo
DURACION_FUNDIDO = 0.45       # segundos al cambiar de fondo
CARPETA = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(CARPETA, "assets")
ARCHIVO_GUARDADO = os.path.join(CARPETA, "partida_guardada.json")
ARCHIVO_FINALES = os.path.join(CARPETA, "finales_descubiertos.json")
POS_X = {"izquierda": 0.24, "centro": 0.5, "derecha": 0.76}
EXTENSIONES = (".png", ".jpg", ".jpeg", ".webp", ".bmp")


def hex_a_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def envolver(texto, fuente, ancho):
    """Parte un texto en líneas que quepan en 'ancho' píxeles."""
    lineas = []
    for parrafo in texto.split("\n"):
        actual = ""
        for palabra in parrafo.split(" "):
            prueba = f"{actual} {palabra}".strip()
            if fuente.size(prueba)[0] <= ancho:
                actual = prueba
            else:
                if actual:
                    lineas.append(actual)
                actual = palabra
        lineas.append(actual)
    return lineas


def buscar_imagen(carpeta, id_):
    for ext in EXTENSIONES:
        ruta = os.path.join(ASSETS, carpeta, id_ + ext)
        if os.path.exists(ruta):
            return ruta
    return None


def panel(superficie, rect, color=(10, 10, 18), alfa=200, radio=18, borde=None):
    capa = pygame.Surface(rect.size, pygame.SRCALPHA)
    pygame.draw.rect(capa, (*color, alfa), capa.get_rect(), border_radius=radio)
    if borde:
        pygame.draw.rect(capa, borde, capa.get_rect(), 2, border_radius=radio)
    superficie.blit(capa, rect.topleft)


class Recursos:
    """Carga (y recuerda) fondos y personajes. Si no hay imagen, los dibuja."""

    def __init__(self, guion):
        self.g = guion
        self._fondos = {}
        self._personajes = {}

    def fondo(self, id_):
        if id_ not in self._fondos:
            ruta = buscar_imagen("fondos", id_) if id_ else None
            if ruta:
                img = pygame.image.load(ruta).convert()
                sup = pygame.transform.smoothscale(img, (ANCHO, ALTO))
            else:
                arriba, abajo = self.g.fondos.get(id_, ("#1a1a26", "#050508"))
                sup = self._degradado(hex_a_rgb(arriba), hex_a_rgb(abajo))
            self._fondos[id_] = sup
        return self._fondos[id_]

    @staticmethod
    def _degradado(c1, c2):
        sup = pygame.Surface((ANCHO, ALTO))
        for y in range(ALTO):
            t = y / (ALTO - 1)
            pygame.draw.line(sup, [round(a + (b - a) * t) for a, b in zip(c1, c2)], (0, y), (ANCHO, y))
        # Viñeta suave en los bordes para dar profundidad
        vineta = pygame.Surface((ANCHO, ALTO), pygame.SRCALPHA)
        for i in range(40):
            pygame.draw.rect(vineta, (0, 0, 0, 4), vineta.get_rect().inflate(-i * 14, -i * 10), 14)
        sup.blit(vineta, (0, 0))
        return sup

    def personaje(self, id_, atenuado=False):
        clave = (id_, atenuado)
        if clave not in self._personajes:
            if (id_, False) not in self._personajes:
                ruta = buscar_imagen("personajes", id_)
                if ruta:
                    img = pygame.image.load(ruta).convert_alpha()
                    alto = int(ALTO * 0.82)
                    img = pygame.transform.smoothscale(img, (int(img.get_width() * alto / img.get_height()), alto))
                else:
                    img = self._silueta(id_)
                self._personajes[(id_, False)] = img
            if atenuado:
                tenue = self._personajes[(id_, False)].copy()
                tenue.fill((115, 115, 130), special_flags=pygame.BLEND_RGB_MULT)
                self._personajes[clave] = tenue
        return self._personajes[clave]

    def _silueta(self, id_):
        """Personaje provisional: una silueta del color del personaje."""
        color = hex_a_rgb(self.g.personajes[id_]["color"])
        oscuro = tuple(int(c * 0.55) for c in color)
        w, h = 320, int(ALTO * 0.78)
        sup = pygame.Surface((w, h), pygame.SRCALPHA)
        pygame.draw.ellipse(sup, oscuro, (30, h * 0.36, w - 60, h * 0.9))       # cuerpo
        pygame.draw.rect(sup, oscuro, (w / 2 - 28, h * 0.27, 56, 70))              # cuello
        pygame.draw.circle(sup, color, (w // 2, int(h * 0.2)), 78)                  # cabeza
        pygame.draw.circle(sup, oscuro, (w // 2, int(h * 0.2)), 78, 4)
        inicial = pygame.font.SysFont("dejavusans,arial", 72, bold=True).render(
            self.g.personajes[id_]["nombre"][0], True, oscuro)
        sup.blit(inicial, inicial.get_rect(center=(w // 2, int(h * 0.2))))
        return sup


class Boton:
    def __init__(self, rect, texto, accion):
        self.rect, self.texto, self.accion = pygame.Rect(rect), texto, accion

    def dibujar(self, pantalla, fuente, raton, numero=None):
        encima = self.rect.collidepoint(raton)
        panel(pantalla, self.rect, (40, 36, 60) if encima else (14, 13, 22), 235 if encima else 210,
              12, (230, 200, 140) if encima else (90, 85, 120))
        etiqueta = f"{numero}.  {self.texto}" if numero else self.texto
        sup = fuente.render(etiqueta, True, (255, 240, 210) if encima else (225, 225, 235))
        pantalla.blit(sup, sup.get_rect(center=self.rect.center))


class Juego:
    def __init__(self, ruta_guion):
        pygame.init()
        self.g = cargar_guion(ruta_guion)
        self.pantalla = pygame.display.set_mode((ANCHO, ALTO))
        pygame.display.set_caption(self.g.titulo)
        self.reloj = pygame.time.Clock()
        fam = "dejavusans,segoeui,arial,helvetica"
        self.f_texto = pygame.font.SysFont(fam, 27)
        self.f_nombre = pygame.font.SysFont(fam, 28, bold=True)
        self.f_boton = pygame.font.SysFont(fam, 25)
        self.f_peq = pygame.font.SysFont(fam, 18)
        self.f_titulo = pygame.font.SysFont("dejavuserif,georgia,timesnewroman", 74, bold=True)
        self.f_sub = pygame.font.SysFont("dejavuserif,georgia,timesnewroman", 30, italic=True)

        self.recursos = Recursos(self.g)
        self.partida = Partida(self.g)
        self.finales = Finales(ARCHIVO_FINALES)
        self.estado = "titulo"          # titulo | finales | juego | final
        self.evento = None
        self.botones = []
        self.historial_abierto = False
        self.historial_scroll = 0
        self.aviso, self.aviso_t = "", 0.0
        self.fondo_actual = self.fondo_anterior = None
        self.fundido = 1.0
        self.t = 0.0
        self.ctrl_t = 0.0
        self.menu_titulo()

    # ----------------------------------------------------------- pantallas
    def menu_titulo(self):
        self.estado = "titulo"
        cx, y = ANCHO // 2 - 170, 380
        opciones = [("Nueva partida", self.nueva_partida)]
        if os.path.exists(ARCHIVO_GUARDADO):
            opciones.append(("Continuar", self.cargar))
        opciones += [("Finales", self.ver_finales), ("Salir", self.salir)]
        self.botones = [Boton((cx, y + i * 70, 340, 54), t, a) for i, (t, a) in enumerate(opciones)]

    def ver_finales(self):
        self.estado = "finales"
        self.botones = [Boton((ANCHO // 2 - 120, ALTO - 90, 240, 52), "Volver", self.menu_titulo)]

    def nueva_partida(self):
        self.partida.reiniciar()
        self.fondo_actual = None
        self.estado = "juego"
        self.avanzar()

    def salir(self):
        pygame.quit()
        sys.exit()

    # -------------------------------------------------------------- lógica
    def avanzar(self):
        try:
            ev = self.partida.siguiente()
        except ErrorGuion as e:
            self.mostrar_aviso(f"Error en el guion: {e}", 8)
            self.menu_titulo()
            return
        self.evento = ev
        self.botones = []
        if self.partida.fondo != self.fondo_actual:
            self.fondo_anterior, self.fondo_actual, self.fundido = self.fondo_actual, self.partida.fondo, 0.0

        if ev["tipo"] == "decir":
            self.lineas = envolver(ev["texto"], self.f_texto, ANCHO - 200)
            self.total_letras = sum(len(l) for l in self.lineas)
            self.letras = 0.0
        elif ev["tipo"] == "elegir":
            n = len(ev["opciones"])
            alto, sep = 56, 14
            y0 = (ALTO - 230) // 2 - (n * (alto + sep)) // 2 + 20
            for k, (indice, texto) in enumerate(ev["opciones"]):
                ancho = max(560, self.f_boton.size(f"9.  {texto}")[0] + 80)
                self.botones.append(Boton((ANCHO // 2 - ancho // 2, y0 + k * (alto + sep), ancho, alto),
                                          texto, lambda i=indice: self.elegir(i)))
            self.lineas = envolver(ev["texto"], self.f_texto, ANCHO - 200) if ev["texto"] else []
            self.total_letras = self.letras = sum(len(l) for l in self.lineas)
        elif ev["tipo"] == "final":
            self.finales.agregar(ev["id"])
            self.estado, self.t_final = "final", 0.0
        else:  # fin_guion
            self.menu_titulo()

    def elegir(self, indice):
        self.partida.elegir(indice)
        self.avanzar()

    def clic_texto(self):
        if self.evento and self.evento["tipo"] == "decir":
            if self.letras < self.total_letras:
                self.letras = self.total_letras     # primer clic: muestra todo
            else:
                self.avanzar()

    def guardar(self):
        if self.estado != "juego":
            return
        with open(ARCHIVO_GUARDADO, "w", encoding="utf-8") as f:
            json.dump(self.partida.a_diccionario(), f, ensure_ascii=False)
        self.mostrar_aviso("Partida guardada")

    def cargar(self):
        try:
            with open(ARCHIVO_GUARDADO, encoding="utf-8") as f:
                self.partida.desde_diccionario(json.load(f))
        except (OSError, ValueError, KeyError, ErrorGuion):
            self.mostrar_aviso("No se pudo cargar la partida")
            return
        self.fondo_actual = None
        self.estado = "juego"
        self.historial_abierto = False
        self.avanzar()
        self.fundido = 0.0
        self.mostrar_aviso("Partida cargada")

    def mostrar_aviso(self, texto, segundos=2.0):
        self.aviso, self.aviso_t = texto, segundos

    # ------------------------------------------------------------- eventos
    def manejar(self, e):
        if e.type == pygame.QUIT:
            self.salir()
        if self.historial_abierto:
            if e.type == pygame.KEYDOWN and e.key in (pygame.K_h, pygame.K_ESCAPE):
                self.historial_abierto = False
            elif e.type == pygame.MOUSEWHEEL:
                self.historial_scroll = max(0, self.historial_scroll + e.y)
            elif e.type == pygame.MOUSEBUTTONDOWN and e.button == 3:
                self.historial_abierto = False
            return

        if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            for b in self.botones:
                if b.rect.collidepoint(e.pos):
                    b.accion()
                    return
            if self.estado == "juego":
                self.clic_texto()
            elif self.estado == "final" and self.t_final > 1.2:
                self.menu_titulo()
        elif e.type == pygame.MOUSEWHEEL and e.y > 0 and self.estado == "juego":
            self.historial_abierto, self.historial_scroll = True, 0
        elif e.type == pygame.KEYDOWN:
            if self.estado == "juego":
                if e.key in (pygame.K_SPACE, pygame.K_RETURN, pygame.K_KP_ENTER):
                    self.clic_texto()
                elif pygame.K_1 <= e.key <= pygame.K_9 and self.evento["tipo"] == "elegir":
                    n = e.key - pygame.K_1
                    if n < len(self.botones):
                        self.botones[n].accion()
                elif e.key == pygame.K_h:
                    self.historial_abierto, self.historial_scroll = True, 0
                elif e.key == pygame.K_F5:
                    self.guardar()
                elif e.key == pygame.K_F9:
                    self.cargar()
                elif e.key == pygame.K_ESCAPE:
                    self.menu_titulo()
            elif self.estado == "final" and self.t_final > 1.2 and e.key in (pygame.K_SPACE, pygame.K_RETURN, pygame.K_ESCAPE):
                self.menu_titulo()
            elif self.estado == "finales" and e.key == pygame.K_ESCAPE:
                self.menu_titulo()
            elif self.estado == "titulo" and e.key == pygame.K_F9:
                self.cargar()

    def actualizar(self, dt):
        self.t += dt
        self.aviso_t = max(0.0, self.aviso_t - dt)
        self.fundido = min(1.0, self.fundido + dt / DURACION_FUNDIDO)
        if self.estado == "final":
            self.t_final += dt
        if self.estado == "juego" and self.evento and self.evento["tipo"] == "decir" and not self.historial_abierto:
            self.letras = min(self.total_letras, self.letras + VELOCIDAD_TEXTO * dt)
            teclas = pygame.key.get_mods()
            if teclas & pygame.KMOD_CTRL:              # adelantar rápido
                self.ctrl_t += dt
                if self.ctrl_t > 0.06:
                    self.ctrl_t = 0.0
                    self.letras = self.total_letras
                    self.avanzar()

    # ------------------------------------------------------------- dibujo
    def dibujar_fondo(self):
        if self.fondo_anterior is not None and self.fundido < 1.0:
            self.pantalla.blit(self.recursos.fondo(self.fondo_anterior), (0, 0))
            nuevo = self.recursos.fondo(self.fondo_actual).copy()
            nuevo.set_alpha(int(255 * self.fundido))
            self.pantalla.blit(nuevo, (0, 0))
        else:
            self.pantalla.blit(self.recursos.fondo(self.fondo_actual), (0, 0))

    def dibujar_personajes(self):
        habla = self.evento.get("quien") if self.evento else None
        orden = sorted(self.partida.visibles.items(), key=lambda kv: kv[0] == habla)
        for id_, pos in orden:
            img = self.recursos.personaje(id_, atenuado=bool(habla) and habla != id_)
            balanceo = math.sin(self.t * 1.6 + hash(id_) % 7) * 3   # "respiración" sutil
            x = int(ANCHO * POS_X[pos]) - img.get_width() // 2
            self.pantalla.blit(img, (x, ALTO - img.get_height() + 30 + balanceo))

    def dibujar_caja_texto(self):
        caja = pygame.Rect(60, ALTO - 210, ANCHO - 120, 180)
        panel(self.pantalla, caja, (8, 8, 16), 215, 18, (70, 66, 100))
        ev = self.evento
        if ev.get("nombre"):
            color = hex_a_rgb(ev["color"])
            nom = self.f_nombre.render(ev["nombre"], True, color)
            etiqueta = pygame.Rect(caja.x + 30, caja.y - 26, nom.get_width() + 40, 48)
            panel(self.pantalla, etiqueta, (14, 12, 24), 245, 12, color)
            self.pantalla.blit(nom, nom.get_rect(center=etiqueta.center))
        restantes = int(self.letras)
        y = caja.y + 36
        italica = not ev.get("nombre") and ev["tipo"] == "decir"
        color_txt = (205, 205, 220) if italica else (245, 245, 250)
        for linea in self.lineas:
            if restantes <= 0:
                break
            parte = linea[:restantes]
            restantes -= len(linea)
            self.f_texto.set_italic(italica)
            self.pantalla.blit(self.f_texto.render(parte, True, color_txt), (caja.x + 40, y))
            y += 36
        self.f_texto.set_italic(False)
        if ev["tipo"] == "decir" and self.letras >= self.total_letras:   # flechita de "continuar"
            yy = caja.bottom - 26 + math.sin(self.t * 5) * 4
            xx = caja.right - 40
            pygame.draw.polygon(self.pantalla, (230, 200, 140), [(xx - 9, yy - 6), (xx + 9, yy - 6), (xx, yy + 6)])

    def dibujar_juego(self, raton):
        self.dibujar_fondo()
        self.dibujar_personajes()
        if self.evento["tipo"] == "elegir":
            velo = pygame.Surface((ANCHO, ALTO), pygame.SRCALPHA)
            velo.fill((0, 0, 0, 90))
            self.pantalla.blit(velo, (0, 0))
            if self.lineas:
                self.dibujar_caja_texto()
            for k, b in enumerate(self.botones, 1):
                b.dibujar(self.pantalla, self.f_boton, raton, k)
        else:
            self.dibujar_caja_texto()
        ayuda = self.f_peq.render("F5 guardar · F9 cargar · H historial · Ctrl adelantar · Esc menú",
                                  True, (200, 200, 215))
        ayuda.set_alpha(110)
        self.pantalla.blit(ayuda, (ANCHO - ayuda.get_width() - 16, 12))
        if self.historial_abierto:
            self.dibujar_historial()

    def dibujar_historial(self):
        velo = pygame.Surface((ANCHO, ALTO), pygame.SRCALPHA)
        velo.fill((5, 5, 10, 225))
        self.pantalla.blit(velo, (0, 0))
        filas = []
        for nombre, texto in self.partida.historial:
            for i, l in enumerate(envolver(texto, self.f_boton, ANCHO - 420)):
                filas.append((nombre if i == 0 else "", l, nombre == "➜"))
            filas.append(("", "", False))
        visibles = (ALTO - 140) // 32
        self.historial_scroll = min(self.historial_scroll, max(0, len(filas) - visibles))
        fin = len(filas) - self.historial_scroll
        y = 70
        for nombre, linea, eleccion in filas[max(0, fin - visibles):fin]:
            color = (230, 200, 140) if eleccion else (225, 225, 235)
            if nombre:
                n = self.f_peq.render("Elegiste" if eleccion else nombre, True, (150, 150, 175))
                self.pantalla.blit(n, (180 - n.get_width(), y + 4))
            self.pantalla.blit(self.f_boton.render(linea, True, color), (210, y))
            y += 32
        pie = self.f_peq.render("Historial — rueda para desplazarte · H o clic derecho para cerrar",
                                True, (150, 150, 175))
        self.pantalla.blit(pie, pie.get_rect(center=(ANCHO // 2, ALTO - 36)))

    def dibujar_titulo(self, raton):
        primer_fondo = next(iter(self.g.fondos), None)
        self.pantalla.blit(self.recursos.fondo(primer_fondo), (0, 0))
        titulo = self.f_titulo.render(self.g.titulo, True, (245, 230, 200))
        sombra = self.f_titulo.render(self.g.titulo, True, (0, 0, 0))
        r = titulo.get_rect(center=(ANCHO // 2, 210 + math.sin(self.t) * 4))
        self.pantalla.blit(sombra, r.move(3, 4))
        self.pantalla.blit(titulo, r)
        n, total = len(self.finales.vistos & set(self.g.finales)), len(self.g.finales)
        sub = self.f_sub.render(f"Finales descubiertos: {n} de {total}", True, (200, 190, 220))
        self.pantalla.blit(sub, sub.get_rect(center=(ANCHO // 2, 300)))
        for b in self.botones:
            b.dibujar(self.pantalla, self.f_boton, raton)

    def dibujar_finales(self, raton):
        self.pantalla.fill((10, 9, 16))
        t = self.f_sub.render("Finales", True, (245, 230, 200))
        self.pantalla.blit(t, t.get_rect(center=(ANCHO // 2, 60)))
        y = 115
        for id_, (titulo, desc) in self.g.finales.items():
            visto = id_ in self.finales.vistos
            fila = pygame.Rect(ANCHO // 2 - 380, y, 760, 74)
            panel(self.pantalla, fila, (24, 22, 36) if visto else (16, 15, 22), 255, 12,
                  (230, 200, 140) if visto else (55, 52, 70))
            nombre = self.f_nombre.render(titulo if visto else "? ? ?", True,
                                          (245, 230, 200) if visto else (110, 105, 130))
            self.pantalla.blit(nombre, (fila.x + 24, fila.y + 10))
            detalle = desc if visto else "Todavía no descubres este final."
            self.pantalla.blit(self.f_peq.render(detalle, True, (170, 165, 190)), (fila.x + 24, fila.y + 46))
            y += 86
        for b in self.botones:
            b.dibujar(self.pantalla, self.f_boton, raton)

    def dibujar_final(self):
        self.dibujar_fondo()
        a = min(1.0, self.t_final / 1.2)
        velo = pygame.Surface((ANCHO, ALTO), pygame.SRCALPHA)
        velo.fill((0, 0, 0, int(215 * a)))
        self.pantalla.blit(velo, (0, 0))
        ev = self.evento
        n_final = list(self.g.finales).index(ev["id"]) + 1
        for texto, fuente, color, y in (
                (f"— FINAL {n_final} DE {len(self.g.finales)} —", self.f_peq, (200, 190, 220), 250),
                (ev["titulo"], self.f_titulo, (245, 230, 200), 330),
                (ev["descripcion"], self.f_sub, (210, 205, 225), 420),
                (f"Has descubierto {len(self.finales.vistos & set(self.g.finales))} de {len(self.g.finales)} finales",
                 self.f_peq, (170, 165, 190), 500)):
            s = fuente.render(texto, True, color)
            s.set_alpha(int(255 * a))
            self.pantalla.blit(s, s.get_rect(center=(ANCHO // 2, y)))
        if self.t_final > 1.2:
            s = self.f_peq.render("Haz clic para volver al menú", True, (150, 150, 175))
            s.set_alpha(int(127 + 127 * math.sin(self.t * 3)))
            self.pantalla.blit(s, s.get_rect(center=(ANCHO // 2, ALTO - 60)))

    def dibujar(self):
        raton = pygame.mouse.get_pos()
        if self.estado == "titulo":
            self.dibujar_titulo(raton)
        elif self.estado == "finales":
            self.dibujar_finales(raton)
        elif self.estado == "juego":
            self.dibujar_juego(raton)
        elif self.estado == "final":
            self.dibujar_final()
        if self.aviso_t > 0:
            s = self.f_boton.render(self.aviso, True, (255, 240, 210))
            r = s.get_rect(midtop=(ANCHO // 2, 24)).inflate(40, 20)
            panel(self.pantalla, r, (30, 26, 44), int(min(1, self.aviso_t) * 230), 10)
            self.pantalla.blit(s, s.get_rect(center=r.center))
        pygame.display.flip()

    def ejecutar(self):
        while True:
            dt = self.reloj.tick(FPS) / 1000
            for e in pygame.event.get():
                self.manejar(e)
            self.actualizar(dt)
            self.dibujar()


if __name__ == "__main__":
    ruta = sys.argv[1] if len(sys.argv) > 1 else os.path.join(CARPETA, "historia.txt")
    try:
        Juego(ruta).ejecutar()
    except ErrorGuion as e:
        print(f"Hay un error en el guion:\n{e}")
        sys.exit(1)
