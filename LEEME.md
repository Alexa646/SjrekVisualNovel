# Motor de novelas visuales en Python

Un motor pequeño para escribir historias con decisiones y varios finales.
La historia se escribe en archivos de texto y el motor se encarga del resto:
textos, personajes, menús, guardado, historial y finales descubiertos.

## Instalación y uso (Ubuntu)

```bash
sudo apt install python3-pygame
python3 juego.py                          # juega historia.txt
python3 juego.py ejemplos/la_ultima_estacion.txt
python3 motor.py historia.txt --revisar   # cuenta decisiones y busca errores
python3 motor.py historia.txt --terminal  # prueba rápida en modo texto
```

**Controles:** clic / Espacio / Enter para avanzar · teclas 1-9 para elegir ·
mantener Ctrl para adelantar · H o rueda del ratón para el historial ·
F5 guardar · F9 cargar · Esc volver al menú.

## Archivos

| Archivo | Qué hace |
|---|---|
| `motor.py` | Lee el guion y lleva el estado (variables, escena actual). No usa pygame. |
| `juego.py` | La parte visual: fondos, personajes, textos, menús y pantallas. |
| `historia.txt` | *El ogro del pantano*: historia fan inspirada en Shrek 1 y 2. 301 decisiones, 14 finales. |
| `capitulos/` | Los 15 capítulos (más 3 aventuras extra) que `historia.txt` incluye. |
| `ejemplos/la_ultima_estacion.txt` | Una historia original más corta, con 6 finales. |

## Cómo escribir una historia

```text
# Esto es un comentario
titulo "Mi historia"

personaje ana "Ana" #ff8fa3          # id, nombre visible, color
fondo_def bosque #2d4a2b #0a140a     # id, color de arriba, color de abajo

incluir capitulos/01.txt             # pegar aquí otro archivo

[inicio]                             # una escena
fondo bosque
mostrar ana izquierda                # izquierda, centro o derecha
Esto es narración.
ana: Y esto lo dice Ana.
$ valor += 1                         # cambiar variables
ana: Tienes {valor} puntos de valor. # mostrar variables en el texto

? ¿Qué haces?                        # un menú
* Seguir a Ana -> seguir | confianza += 1     # salta a otra escena
* (si valor >= 2) Entrar a la cueva -> cueva  # solo aparece si se cumple
* Saludar | confianza += 1                    # sin "->": la historia sigue abajo
si eleccion == 3: ana: ¡Hola a ti también!    # reaccionar a la opción elegida

si confianza >= 3 -> final_bueno     # salto condicional
si confianza < 0: ana: No confío en ti.   # línea condicional
ocultar ana                          # o: ocultar todos
ir otra_escena                       # salto directo

[final_bueno]
final bueno "Amistad" "Confiaste en Ana."   # id, título, descripción
```

**Reglas clave**

- `nombre: texto` es diálogo **solo si** ese nombre se definió con `personaje`. Si no, es narración.
- Las variables empiezan en 0. Puedes usar `verdadero`/`falso`, `and`, `or`, `not`, `min()`, `max()`.
- Tras cada menú, la variable `eleccion` vale 1, 2, 3… según la opción elegida.
- Varias operaciones se separan con comas: `$ visitas += 1, llave = verdadero`.
- Si una escena termina sin `ir`, menú ni `final`, sigue con la escena de abajo.
- `--revisar` te dice cuántas decisiones tiene tu historia y si hay escenas inalcanzables.

## Variables de *El ogro del pantano*

`amor` (Fiona), `amistad` (Burro), `valor`, `cuentos` (criaturas de cuento),
`gruñon`, `fama`, `dragona`, `suegro` (rey Harold), `reina`, `gato`, `sospecha`.
Cada final depende de una combinación de ellas.

## Nota

*El ogro del pantano* es una historia fan con diálogos originales. Los personajes
pertenecen a DreamWorks: está bien para jugarla o compartirla entre amigos,
pero no para publicarla o venderla.
