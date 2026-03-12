import os
#Estos import sirven para el guardado de datos
import json
import random
from datetime import datetime
from pathlib import Path

#Estos import son utilizados como interfaces visuales
import tkinter as tk
from tkinter import ttk, messagebox

#Se lo usa para armar la interfaz interactiva con el usuario
import pygame

# ============================================================
# OPENREHAB ACV - ÁREA 1 (VISIÓN Y PERCEPCIÓN)
# ------------------------------------------------------------
# Este archivo implementa un esqueleto funcional del flujo pedido:
#
#   Pantalla inicio (Tkinter)
#       ↓
#   Ingresar paciente
#       ↓
#   Botón "Comenzar test"
#       ↓
#   Se abre actividad en Pygame
#       ↓
#   Termina test
#       ↓
#   Se guarda JSON
#       ↓
#   Volver a Tkinter

# -----------------------------
# CONFIGURACIÓN GENERAL
# -----------------------------
APP_TITLE = "OpenRehab ACV"
RESULTS_DIR = Path("results")
RESULTS_DIR.mkdir(exist_ok=True)

# Diccionario con los tests del Área 1, 2 y 3.
# La clave (key) sirve como identificador interno.
# El valor visible se usa en la interfaz.
AREA_1_TESTS = {
    "exploracion_faro": "1. Exploración de Faro (Neglect)",
    "anclaje_visual": "2. Anclaje Visual",
    "complejidad_gradual": "3. Complejidad Gradual (DVC)",
    "cancelacion_estimulos": "4. Cancelación de Estímulos",
    "figura_fondo": "5. Figura-Fondo",
    "acinetopsia": "6. Acinetopsia (Movimiento)",
}
AREA_2_TESTS = {
    "estabilizador_trayectoria": "7. Estabilizador de Trayectoria",
    "ley_de_fitts": "8. Ley de Fitts",
    "barrido_ritmico": "9. Barrido Rítmico (Scanning)",
    "arrastre_sostenido": "10. Arrastre Sostenido (Drag & Drop)",
    "reaccion_multimodal": "11. Reacción Multimodal",
    "ganancia_adaptativa": "12. Ganancia Adaptativa",
}

AREA_3_TESTS = {
    "denominacion_fonologica": "13. Denominación Fonológica",
    "memoria_n_back": "14. Memoria N-Back",
    "efecto_stroop": "15. Efecto Stroop (Inhibición)",
    "completamiento_semantico": "16. Completamiento Semántico",
    "intruso_logico": "17. Intruso Lógico",
    "secuenciacion_avd": "18. Secuenciación AVD",
}


# ============================================================
# FUNCIONES DE DATOS / JSON
# ============================================================

#Construye un nombre de archivo único para cada resultado. No sobreescribe archivos.
#Crea el nombre y lo ubica en la carpeta results
def build_result_filename(patient_id: str, test_key: str) -> Path:
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{patient_id}_{test_key}_{timestamp}.json"
    return RESULTS_DIR / filename


#Guarda el resultado. Se ejecuta cuando termina el pygame.
def save_result_json(patient_id: str, test_key: str, metric_value, unit: str, attempts: int):



    payload = {
        "id_paciente": patient_id,
        "fecha": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "test": test_key,
        "metrica_principal": metric_value,
        "unidad": unit,
        "intentos": attempts,
    }

    path = build_result_filename(patient_id, test_key)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=4)

    return path

#Muestra un historal de pruebas del paciente según el id.
def load_patient_results(patient_id: str):

    results = []

    for file_path in RESULTS_DIR.glob(f"{patient_id}_*.json"):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                data["__file"] = str(file_path)
                results.append(data)
        except Exception:
            # Si algún JSON estuviera corrupto, no frenamos el programa.
            # Simplemente ignoramos ese archivo.
            pass

    # Ordenamos por fecha descendente si existe el campo.
    results.sort(key=lambda x: x.get("fecha", ""), reverse=True)
    return results

#Devuelve el último resultado encontrado para un test específico.
def get_last_result_for_test(patient_id: str, test_key: str):
    
    results = load_patient_results(patient_id)
    for result in results:
        if result.get("test") == test_key:
            return result
    return None


# ============================================================
# MOTOR BASE PYGAME PARA LOS TESTS
# ============================================================

#Esta función ejecuta el test interactivo en Pygame, mide el
#desempeño del paciente y guarda el resultado en un archivo JSON.

def run_pygame_test(patient_id: str, test_key: str, test_name: str):
      
    pygame.init()

    # Tamaño de ventana base. Puede ajustarse luego.
    width, height = 1100, 700
    screen = pygame.display.set_mode((width, height))
    pygame.display.set_caption(f"{APP_TITLE} - {test_name}")

    # Fuente base para textos.
    font = pygame.font.SysFont("arial", 28)
    small_font = pygame.font.SysFont("arial", 22)
    big_font = pygame.font.SysFont("arial", 42, bold=True)

    # Reloj para controlar FPS.
    clock = pygame.time.Clock()

    # -----------------------------
    # VARIABLES DEL TEST DEMO
    # -----------------------------
    # Estados posibles del flujo dentro del minijuego:
    # - intro: pantalla de instrucciones
    # - playing: test corriendo
    # - result: pantalla final
    state = "intro"

    # Duración del test demo en segundos.
    duration_seconds = 20

    # Tiempo de inicio del juego, se setea al empezar.
    start_ticks = None

    # Métricas demo.
    hits = 0
    misses = 0
    attempts = 1

    # Creamos targets circulares para clicar.
    # En la versión real de cada test esto cambia mucho.
    targets = []
    for _ in range(10):
        radius = random.randint(20, 45)
        x = random.randint(100, width - 100)
        y = random.randint(140, height - 80)
        targets.append({"x": x, "y": y, "r": radius, "active": True})

    # Resultado final y path del JSON guardado.
    final_metric = None
    final_unit = "aciertos"
    saved_path = None

    def reset_targets():
        """Regenera los targets al azar."""
        for t in targets:
            t["x"] = random.randint(100, width - 100)
            t["y"] = random.randint(140, height - 80)
            t["r"] = random.randint(20, 45)
            t["active"] = True

    def draw_intro():
        """Dibuja la pantalla inicial del test dentro de Pygame."""
        screen.fill((15, 18, 25))

        title = big_font.render(test_name, True, (240, 240, 240))
        subtitle = font.render("Demo base del test - Área 1", True, (210, 210, 210))
        info_1 = small_font.render(f"Paciente: {patient_id}", True, (255, 220, 120))
        info_2 = small_font.render("Instrucción demo: hacé click sobre los círculos visibles.", True, (220, 220, 220))
        info_3 = small_font.render("Presioná ESPACIO para comenzar.", True, (120, 255, 180))
        info_4 = small_font.render("Presioná ESC para salir y volver al menú.", True, (255, 160, 160))

        screen.blit(title, (60, 70))
        screen.blit(subtitle, (60, 140))
        screen.blit(info_1, (60, 220))
        screen.blit(info_2, (60, 270))
        screen.blit(info_3, (60, 315))
        screen.blit(info_4, (60, 360))

        # Caja visual estilo panel de instrucciones.
        pygame.draw.rect(screen, (45, 50, 65), pygame.Rect(55, 200, 850, 210), border_radius=16)
        pygame.draw.rect(screen, (220, 220, 220), pygame.Rect(55, 200, 850, 210), 2, border_radius=16)

        # Reescribimos encima para asegurar que el panel quede atrás.
        screen.blit(info_1, (80, 230))
        screen.blit(info_2, (80, 275))
        screen.blit(info_3, (80, 320))
        screen.blit(info_4, (80, 365))

    def draw_playing():
        """Dibuja la pantalla del juego mientras el test corre."""
        screen.fill((245, 245, 245))

        elapsed = (pygame.time.get_ticks() - start_ticks) / 1000
        remaining = max(0, duration_seconds - elapsed)

        # Barra superior informativa.
        pygame.draw.rect(screen, (25, 25, 25), pygame.Rect(0, 0, width, 90))

        title = font.render(test_name, True, (255, 255, 255))
        score = small_font.render(f"Aciertos: {hits} | Errores: {misses}", True, (255, 255, 255))
        timer = small_font.render(f"Tiempo restante: {remaining:0.1f}s", True, (255, 230, 120))

        screen.blit(title, (25, 20))
        screen.blit(score, (25, 55))
        screen.blit(timer, (820, 32))

        # Dibujamos targets activos.
        for target in targets:
            if target["active"]:
                pygame.draw.circle(screen, (30, 144, 255), (target["x"], target["y"]), target["r"])
                pygame.draw.circle(screen, (10, 10, 10), (target["x"], target["y"]), target["r"], 3)

    def draw_result():
        """Dibuja la pantalla final con resultado y confirmación de guardado."""
        screen.fill((18, 24, 32))

        title = big_font.render("Resultado guardado", True, (220, 255, 220))
        metric = font.render(f"Métrica principal: {final_metric} {final_unit}", True, (240, 240, 240))
        errors = font.render(f"Errores registrados: {misses}", True, (240, 240, 240))
        file_text = small_font.render(f"Archivo: {saved_path}", True, (180, 210, 255)) if saved_path else None
        back = small_font.render("Presioná ENTER o ESC para volver al menú.", True, (255, 220, 120))

        screen.blit(title, (60, 80))
        screen.blit(metric, (60, 180))
        screen.blit(errors, (60, 235))
        if file_text:
            screen.blit(file_text, (60, 300))
        screen.blit(back, (60, 380))

    running = True

    while running:
        # -------------------------------------------
        # MANEJO DE EVENTOS (teclado, mouse, cierre)
        # -------------------------------------------
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            elif event.type == pygame.KEYDOWN:
                # ESC cierra y vuelve a Tkinter.
                if event.key == pygame.K_ESCAPE:
                    running = False

                # Desde intro, ESPACIO empieza el juego.
                elif state == "intro" and event.key == pygame.K_SPACE:
                    state = "playing"
                    start_ticks = pygame.time.get_ticks()
                    hits = 0
                    misses = 0
                    reset_targets()

                # Desde pantalla final, ENTER vuelve al menú.
                elif state == "result" and event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                    running = False

            elif event.type == pygame.MOUSEBUTTONDOWN and state == "playing":
                # Registramos clicks sobre los círculos.
                mouse_x, mouse_y = event.pos
                clicked_target = False

                for target in targets:
                    if not target["active"]:
                        continue

                    dx = mouse_x - target["x"]
                    dy = mouse_y - target["y"]
                    inside = (dx * dx + dy * dy) <= (target["r"] * target["r"])

                    if inside:
                        target["active"] = False
                        hits += 1
                        clicked_target = True
                        break

                # Si clickeó fuera de todo target, lo contamos como error.
                if not clicked_target:
                    misses += 1

        # -------------------------------------------
        # LÓGICA DE ACTUALIZACIÓN
        # -------------------------------------------
        if state == "playing":
            elapsed = (pygame.time.get_ticks() - start_ticks) / 1000

            # Si se desactivaron todos los targets, regeneramos más.
            if all(not t["active"] for t in targets):
                reset_targets()

            # Cuando termina el tiempo, calculamos resultado y guardamos JSON.
            if elapsed >= duration_seconds:
                final_metric = hits
                final_unit = "aciertos"
                saved_path = save_result_json(
                    patient_id=patient_id,
                    test_key=test_key,
                    metric_value=final_metric,
                    unit=final_unit,
                    attempts=attempts,
                )
                state = "result"

        # -------------------------------------------
        # DIBUJADO SEGÚN EL ESTADO ACTUAL
        # -------------------------------------------
        if state == "intro":
            draw_intro()
        elif state == "playing":
            draw_playing()
        elif state == "result":
            draw_result()

        pygame.display.flip()
        clock.tick(60)

    pygame.quit()


# =================================================================
# CREACIÓN DE CADA MODO DE JUEGO
# =================================================================
def run_exploracion_faro_test(patient_id: str, test_key: str, test_name: str):
    
    pygame.init()

    width, height = 1200, 750
    screen = pygame.display.set_mode((width, height))
    pygame.display.set_caption(f"{APP_TITLE} - {test_name}")

    clock = pygame.time.Clock()

    title_font = pygame.font.SysFont("arial", 34, bold=True)
    font = pygame.font.SysFont("arial", 24)
    small_font = pygame.font.SysFont("arial", 20)

    state = "intro"
    duration_seconds = 30
    start_ticks = None

    flashlight_radius = 120
    total_objects = 12

    objects = []

    found_count = 0
    left_found = 0
    right_found = 0
    attempts = 1
    saved_path = None
    final_metric = 0
    final_unit = "objetos_encontrados"

    def generate_objects():

        generated = []

        left_count = total_objects // 2
        right_count = total_objects - left_count

        for _ in range(left_count):
            generated.append({
                "x": random.randint(80, width // 2 - 80),
                "y": random.randint(140, height - 80),
                "r": random.randint(18, 28),
                "found": False,
                "side": "left"
            })

        for _ in range(right_count):
            generated.append({
                "x": random.randint(width // 2 + 80, width - 80),
                "y": random.randint(140, height - 80),
                "r": random.randint(18, 28),
                "found": False,
                "side": "right"
            })

        return generated

    objects = generate_objects()

    def draw_intro():

        screen.fill((12, 16, 24))

        title = title_font.render(test_name, True, (240, 240, 240))
        info1 = font.render(f"Paciente: {patient_id}", True, (255, 220, 120))
        info2 = font.render("El cursor funciona como una linterna.", True, (220, 220, 220))
        info3 = font.render("Explorá la pantalla y encontrá los objetos ocultos.", True, (220, 220, 220))
        info4 = font.render("Hacé click cuando detectes un objeto.", True, (220, 220, 220))
        info5 = font.render("Presioná ESPACIO para comenzar.", True, (120, 255, 180))
        info6 = font.render("ESC para volver.", True, (255, 160, 160))

        screen.blit(title, (60, 70))
        screen.blit(info1, (60, 200))
        screen.blit(info2, (60, 240))
        screen.blit(info3, (60, 280))
        screen.blit(info4, (60, 320))
        screen.blit(info5, (60, 380))
        screen.blit(info6, (60, 420))

    def draw_playing():

        screen.fill((18, 18, 18))

        pygame.draw.rect(screen, (25, 25, 25), pygame.Rect(0, 0, width, 90))
        pygame.draw.line(screen, (70, 70, 70), (width // 2, 90), (width // 2, height), 1)

        elapsed = (pygame.time.get_ticks() - start_ticks) / 1000
        remaining = max(0, duration_seconds - elapsed)

        title = font.render(test_name, True, (255, 255, 255))
        info = small_font.render(
            f"Encontrados: {found_count}/{total_objects}   |   Tiempo restante: {remaining:0.1f}s",
            True,
            (255, 230, 120)
        )

        screen.blit(title, (20, 18))
        screen.blit(info, (20, 55))

        for obj in objects:
            if obj["found"]:
                pygame.draw.circle(screen, (80, 220, 120), (obj["x"], obj["y"]), obj["r"])

        mouse_x, mouse_y = pygame.mouse.get_pos()

        for obj in objects:
            if obj["found"]:
                continue

            dx = mouse_x - obj["x"]
            dy = mouse_y - obj["y"]
            distance_sq = dx * dx + dy * dy

            if distance_sq <= flashlight_radius * flashlight_radius:
                pygame.draw.circle(screen, (240, 220, 90), (obj["x"], obj["y"]), obj["r"])

        darkness = pygame.Surface((width, height), pygame.SRCALPHA)
        darkness.fill((0, 0, 0, 210))

        pygame.draw.circle(darkness, (0, 0, 0, 0), (mouse_x, mouse_y), flashlight_radius)

        screen.blit(darkness, (0, 0))

        pygame.draw.circle(screen, (255, 255, 180), (mouse_x, mouse_y), flashlight_radius, 2)

    def draw_result():

        screen.fill((16, 22, 30))

        title = title_font.render("Resultado guardado", True, (220, 255, 220))
        line1 = font.render(f"Métrica principal: {final_metric} {final_unit}", True, (240, 240, 240))
        line2 = font.render("Presioná ENTER o ESC para volver.", True, (255, 220, 120))

        screen.blit(title, (60, 100))
        screen.blit(line1, (60, 200))
        screen.blit(line2, (60, 300))

    running = True

    while running:

        for event in pygame.event.get():

            if event.type == pygame.QUIT:
                running = False

            elif event.type == pygame.KEYDOWN:

                if event.key == pygame.K_ESCAPE:
                    running = False

                elif state == "intro" and event.key == pygame.K_SPACE:
                    state = "playing"
                    start_ticks = pygame.time.get_ticks()

                elif state == "result" and event.key == pygame.K_RETURN:
                    running = False

            elif event.type == pygame.MOUSEBUTTONDOWN and state == "playing":

                mouse_x, mouse_y = event.pos

                for obj in objects:

                    if obj["found"]:
                        continue

                    dx = mouse_x - obj["x"]
                    dy = mouse_y - obj["y"]
                    inside = (dx * dx + dy * dy) <= (obj["r"] * obj["r"])

                    if inside:
                        obj["found"] = True
                        found_count += 1

                        if obj["side"] == "left":
                            left_found += 1
                        else:
                            right_found += 1
                        break

        if state == "playing":

            elapsed = (pygame.time.get_ticks() - start_ticks) / 1000

            if found_count == total_objects or elapsed >= duration_seconds:

                final_metric = found_count

                saved_path = save_result_json(
                    patient_id,
                    test_key,
                    final_metric,
                    final_unit,
                    attempts
                )

                state = "result"

        if state == "intro":
            draw_intro()

        elif state == "playing":
            draw_playing()

        elif state == "result":
            draw_result()

        pygame.display.flip()
        clock.tick(60)

    pygame.quit()

def run_anclaje_visual_test(patient_id: str, test_key: str, test_name: str):
    
    pygame.init()

    width, height = 1200, 750
    screen = pygame.display.set_mode((width, height))
    pygame.display.set_caption(f"{APP_TITLE} - {test_name}")

    clock = pygame.time.Clock()

    font = pygame.font.SysFont("arial", 28)
    title_font = pygame.font.SysFont("arial", 36, bold=True)

    state = "intro"

    trials = 6
    current_trial = 0

    bar_clicked = False

    start_ticks = None

    attempts = 1
    saved_path = None
    final_metric = 0
    final_unit = "anclajes_correctos"

    sentences = [
        "El perro corre en el parque.",
        "La casa tiene una puerta azul.",
        "Hoy el clima está muy agradable.",
        "El tren llega a la estación.",
        "Los niños juegan en el patio.",
        "La doctora revisa al paciente."
    ]

    bar_flash_timer = 0

    def draw_intro():

        screen.fill((20, 24, 32))

        title = title_font.render(test_name, True, (240,240,240))
        info1 = font.render("Tocá la barra roja del lado izquierdo para habilitar el texto.", True, (220,220,220))
        info2 = font.render("Esto entrena la atención al margen izquierdo.", True, (220,220,220))
        info3 = font.render("Presioná ESPACIO para comenzar.", True, (120,255,180))

        screen.blit(title,(60,80))
        screen.blit(info1,(60,200))
        screen.blit(info2,(60,250))
        screen.blit(info3,(60,350))

    def draw_playing():

        nonlocal bar_flash_timer

        screen.fill((240,240,240))

        pygame.draw.rect(screen,(230,230,230),(0,0,width,80))

        title = font.render(f"Intento {current_trial+1} / {trials}",True,(20,20,20))
        screen.blit(title,(20,25))

        bar_flash_timer += 1

        bar_color = (255,60,60)

        if (bar_flash_timer//30)%2 == 0:
            pygame.draw.rect(screen,bar_color,(20,150,30,400))

        if bar_clicked:

            text_surface = font.render(sentences[current_trial],True,(0,0,0))
            screen.blit(text_surface,(200,300))

            pygame.draw.rect(screen,(80,160,255),(900,500,180,60))
            next_text = font.render("Siguiente",True,(255,255,255))
            screen.blit(next_text,(930,515))

    def draw_result():

        screen.fill((20,30,40))

        title = title_font.render("Resultado guardado",True,(220,255,220))
        line1 = font.render(f"Métrica principal: {final_metric}",True,(240,240,240))
        line2 = font.render("ENTER o ESC para volver",True,(255,220,120))

        screen.blit(title,(80,120))
        screen.blit(line1,(80,240))
        screen.blit(line2,(80,320))

    running = True

    while running:

        for event in pygame.event.get():

            if event.type == pygame.QUIT:
                running=False

            elif event.type == pygame.KEYDOWN:

                if event.key == pygame.K_ESCAPE:
                    running=False

                elif state=="intro" and event.key==pygame.K_SPACE:
                    state="playing"
                    start_ticks = pygame.time.get_ticks()

                elif state=="result" and event.key==pygame.K_RETURN:
                    running=False

            elif event.type == pygame.MOUSEBUTTONDOWN and state=="playing":

                mouse_x, mouse_y = event.pos

                if not bar_clicked:

                    if 20 <= mouse_x <= 50 and 150 <= mouse_y <= 550:
                        bar_clicked=True

                else:

                    if 900 <= mouse_x <= 1080 and 500 <= mouse_y <= 560:

                        current_trial +=1
                        bar_clicked=False

                        if current_trial >= trials:

                            final_metric = trials

                            saved_path = save_result_json(
                                patient_id,
                                test_key,
                                final_metric,
                                final_unit,
                                attempts
                            )

                            state="result"

        if state=="intro":
            draw_intro()

        elif state=="playing":
            draw_playing()

        elif state=="result":
            draw_result()

        pygame.display.flip()
        clock.tick(60)

    pygame.quit()

def run_complejidad_gradual_test(patient_id: str, test_key: str, test_name: str):
    
    pygame.init()

    width, height = 1200, 750
    screen = pygame.display.set_mode((width, height))
    pygame.display.set_caption(f"{APP_TITLE} - {test_name}")

    clock = pygame.time.Clock()

    title_font = pygame.font.SysFont("arial", 34, bold=True)
    font = pygame.font.SysFont("arial", 24)
    big_font = pygame.font.SysFont("arial", 64, bold=True)

    state = "intro"
    attempts = 1
    saved_path = None
    final_metric = 0
    final_unit = "niveles_superados"

    levels = 6
    current_level = 0

    target_shapes = ["▲", "■", "●"]
    current_target = random.choice(target_shapes)

    target_rect = None
    distractor_rects = []

    def generate_level(level_index):
        """
        Genera un nivel con un target y varios distractores.
        A mayor nivel, más distractores y más cercanía visual.
        """
        nonlocal target_rect, distractor_rects, current_target

        current_target = random.choice(target_shapes)
        distractor_rects = []

        cols = 5 + level_index
        rows = 3 + level_index // 2
        cell_w = 110
        cell_h = 90
        start_x = 120
        start_y = 170

        all_cells = []
        for r in range(rows):
            for c in range(cols):
                x = start_x + c * cell_w
                y = start_y + r * cell_h
                all_cells.append(pygame.Rect(x, y, 80, 60))

        random.shuffle(all_cells)
        target_rect = all_cells[0]

        for rect in all_cells[1:]:
            distractor_rects.append(rect)

    generate_level(current_level)

    def draw_intro():
        screen.fill((18, 24, 32))

        t1 = title_font.render(test_name, True, (240, 240, 240))
        t2 = font.render("Encontrá la figura objetivo entre distractores.", True, (220, 220, 220))
        t3 = font.render("La dificultad aumenta en cada nivel.", True, (220, 220, 220))
        t4 = font.render("Presioná ESPACIO para comenzar.", True, (120, 255, 180))

        screen.blit(t1, (60, 70))
        screen.blit(t2, (60, 200))
        screen.blit(t3, (60, 245))
        screen.blit(t4, (60, 330))

    def draw_playing():
        screen.fill((245, 245, 245))

        pygame.draw.rect(screen, (30, 30, 30), pygame.Rect(0, 0, width, 90))

        header = font.render(f"Nivel {current_level + 1}/{levels}", True, (255, 255, 255))
        instruction = font.render(f"Hacé click sobre: {current_target}", True, (255, 230, 120))

        screen.blit(header, (20, 18))
        screen.blit(instruction, (20, 52))

        # Target
        pygame.draw.rect(screen, (230, 230, 230), target_rect, border_radius=10)
        target_text = big_font.render(current_target, True, (20, 20, 20))
        screen.blit(target_text, (target_rect.x + 18, target_rect.y - 5))

        # Distractores
        for rect in distractor_rects:
            pygame.draw.rect(screen, (235, 235, 235), rect, border_radius=10)

            if current_target == "▲":
                distractor_symbol = random.choice(["△", "●", "■"])
            elif current_target == "■":
                distractor_symbol = random.choice(["□", "▲", "●"])
            else:
                distractor_symbol = random.choice(["○", "▲", "■"])

            color_value = max(80, 180 - current_level * 12)
            txt = big_font.render(distractor_symbol, True, (color_value, color_value, color_value))
            screen.blit(txt, (rect.x + 18, rect.y - 5))

    def draw_result():
        screen.fill((18, 24, 32))

        t1 = title_font.render("Resultado guardado", True, (220, 255, 220))
        t2 = font.render(f"Métrica principal: {final_metric} {final_unit}", True, (240, 240, 240))
        t3 = font.render("Presioná ENTER o ESC para volver.", True, (255, 220, 120))

        screen.blit(t1, (60, 100))
        screen.blit(t2, (60, 200))
        screen.blit(t3, (60, 280))

    running = True

    while running:
        for event in pygame.event.get():

            if event.type == pygame.QUIT:
                running = False

            elif event.type == pygame.KEYDOWN:

                if event.key == pygame.K_ESCAPE:
                    running = False

                elif state == "intro" and event.key == pygame.K_SPACE:
                    state = "playing"

                elif state == "result" and event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                    running = False

            elif event.type == pygame.MOUSEBUTTONDOWN and state == "playing":

                mouse_x, mouse_y = event.pos

                if target_rect.collidepoint(mouse_x, mouse_y):
                    current_level += 1

                    if current_level >= levels:
                        final_metric = levels
                        saved_path = save_result_json(
                            patient_id,
                            test_key,
                            final_metric,
                            final_unit,
                            attempts
                        )
                        state = "result"
                    else:
                        generate_level(current_level)

        if state == "intro":
            draw_intro()
        elif state == "playing":
            draw_playing()
        elif state == "result":
            draw_result()

        pygame.display.flip()
        clock.tick(60)

    pygame.quit()

def run_cancelacion_estimulos_test(patient_id: str, test_key: str, test_name: str):
    
    pygame.init()

    width, height = 1200, 760
    screen = pygame.display.set_mode((width, height))
    pygame.display.set_caption(f"{APP_TITLE} - {test_name}")

    clock = pygame.time.Clock()

    title_font = pygame.font.SysFont("arial", 34, bold=True)
    font = pygame.font.SysFont("arial", 24)
    cell_font = pygame.font.SysFont("arial", 34, bold=True)

    state = "intro"
    attempts = 1
    final_metric = 0
    final_unit = "objetivos_encontrados"

    rows, cols = 7, 10
    cell_size = 70
    start_x = 130
    start_y = 150

    grid = []
    total_targets = 0
    found_targets = 0

    def generate_grid():
        """
        Genera una matriz de símbolos con objetivos X y distractores O.
        """
        nonlocal grid, total_targets

        grid = []
        total_targets = 0

        for r in range(rows):
            row = []
            for c in range(cols):
                is_target = random.random() < 0.28
                symbol = "X" if is_target else "O"
                if is_target:
                    total_targets += 1

                rect = pygame.Rect(
                    start_x + c * cell_size,
                    start_y + r * cell_size,
                    cell_size - 8,
                    cell_size - 8
                )

                row.append({
                    "symbol": symbol,
                    "clicked": False,
                    "rect": rect
                })
            grid.append(row)

    generate_grid()

    def draw_intro():
        screen.fill((18, 24, 32))

        t1 = title_font.render(test_name, True, (240, 240, 240))
        t2 = font.render("Hacé click en todas las X de la matriz.", True, (220, 220, 220))
        t3 = font.render("Presioná ESPACIO para comenzar.", True, (120, 255, 180))

        screen.blit(t1, (60, 70))
        screen.blit(t2, (60, 210))
        screen.blit(t3, (60, 290))

    def draw_playing():
        screen.fill((245, 245, 245))

        pygame.draw.rect(screen, (30, 30, 30), pygame.Rect(0, 0, width, 90))

        h1 = font.render(f"Objetivos encontrados: {found_targets}/{total_targets}", True, (255, 255, 255))
        h2 = font.render("Objetivo: clickear todas las X", True, (255, 230, 120))

        screen.blit(h1, (20, 18))
        screen.blit(h2, (20, 52))

        for row in grid:
            for cell in row:
                color = (230, 230, 230)
                if cell["clicked"] and cell["symbol"] == "X":
                    color = (140, 220, 140)
                elif cell["clicked"] and cell["symbol"] != "X":
                    color = (235, 140, 140)

                pygame.draw.rect(screen, color, cell["rect"], border_radius=8)
                pygame.draw.rect(screen, (50, 50, 50), cell["rect"], 2, border_radius=8)

                txt = cell_font.render(cell["symbol"], True, (20, 20, 20))
                screen.blit(txt, (cell["rect"].x + 20, cell["rect"].y + 10))

    def draw_result():
        screen.fill((18, 24, 32))

        t1 = title_font.render("Resultado guardado", True, (220, 255, 220))
        t2 = font.render(f"Métrica principal: {final_metric} {final_unit}", True, (240, 240, 240))
        t3 = font.render("Presioná ENTER o ESC para volver.", True, (255, 220, 120))

        screen.blit(t1, (60, 100))
        screen.blit(t2, (60, 200))
        screen.blit(t3, (60, 280))

    running = True

    while running:
        for event in pygame.event.get():

            if event.type == pygame.QUIT:
                running = False

            elif event.type == pygame.KEYDOWN:

                if event.key == pygame.K_ESCAPE:
                    running = False

                elif state == "intro" and event.key == pygame.K_SPACE:
                    state = "playing"

                elif state == "result" and event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                    running = False

            elif event.type == pygame.MOUSEBUTTONDOWN and state == "playing":

                mouse_x, mouse_y = event.pos

                for row in grid:
                    for cell in row:
                        if cell["rect"].collidepoint(mouse_x, mouse_y) and not cell["clicked"]:
                            cell["clicked"] = True
                            if cell["symbol"] == "X":
                                found_targets += 1

        if state == "playing":
            if found_targets >= total_targets:
                final_metric = found_targets
                save_result_json(
                    patient_id,
                    test_key,
                    final_metric,
                    final_unit,
                    attempts
                )
                state = "result"

        if state == "intro":
            draw_intro()
        elif state == "playing":
            draw_playing()
        elif state == "result":
            draw_result()

        pygame.display.flip()
        clock.tick(60)

    pygame.quit()

def run_figura_fondo_test(patient_id: str, test_key: str, test_name: str):
    
    pygame.init()

    width, height = 1200, 750
    screen = pygame.display.set_mode((width, height))
    pygame.display.set_caption(f"{APP_TITLE} - {test_name}")

    clock = pygame.time.Clock()

    title_font = pygame.font.SysFont("arial", 34, bold=True)
    font = pygame.font.SysFont("arial", 24)

    state = "intro"
    attempts = 1
    final_metric = 0
    final_unit = "figuras_detectadas"

    rounds = 5
    current_round = 0

    target_rect = pygame.Rect(0, 0, 0, 0)
    buttons = []

    def generate_round():
        """
        Genera una figura de bajo contraste y opciones de respuesta.
        """
        nonlocal target_rect, buttons

        x = random.randint(220, 800)
        y = random.randint(180, 430)
        w = random.randint(140, 220)
        h = random.randint(80, 150)

        target_rect = pygame.Rect(x, y, w, h)

        buttons = [
            {"label": "Rectángulo", "rect": pygame.Rect(180, 580, 200, 60)},
            {"label": "Círculo", "rect": pygame.Rect(470, 580, 200, 60)},
            {"label": "Triángulo", "rect": pygame.Rect(760, 580, 200, 60)},
        ]

    generate_round()

    def draw_intro():
        screen.fill((20, 24, 32))

        t1 = title_font.render(test_name, True, (240, 240, 240))
        t2 = font.render("Identificá la figura con bajo contraste respecto al fondo.", True, (220, 220, 220))
        t3 = font.render("Presioná ESPACIO para comenzar.", True, (120, 255, 180))

        screen.blit(t1, (60, 70))
        screen.blit(t2, (60, 210))
        screen.blit(t3, (60, 290))

    def draw_playing():
        screen.fill((205, 205, 205))

        pygame.draw.rect(screen, (190, 190, 190), target_rect, border_radius=14)
        pygame.draw.rect(screen, (198, 198, 198), target_rect.inflate(-8, -8), border_radius=14)

        header = font.render(f"Ronda {current_round + 1}/{rounds}", True, (30, 30, 30))
        screen.blit(header, (40, 30))

        for button in buttons:
            pygame.draw.rect(screen, (80, 160, 255), button["rect"], border_radius=12)
            txt = font.render(button["label"], True, (255, 255, 255))
            screen.blit(txt, (button["rect"].x + 35, button["rect"].y + 16))

    def draw_result():
        screen.fill((18, 24, 32))

        t1 = title_font.render("Resultado guardado", True, (220, 255, 220))
        t2 = font.render(f"Métrica principal: {final_metric} {final_unit}", True, (240, 240, 240))
        t3 = font.render("Presioná ENTER o ESC para volver.", True, (255, 220, 120))

        screen.blit(t1, (60, 100))
        screen.blit(t2, (60, 200))
        screen.blit(t3, (60, 280))

    running = True

    while running:
        for event in pygame.event.get():

            if event.type == pygame.QUIT:
                running = False

            elif event.type == pygame.KEYDOWN:

                if event.key == pygame.K_ESCAPE:
                    running = False

                elif state == "intro" and event.key == pygame.K_SPACE:
                    state = "playing"

                elif state == "result" and event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                    running = False

            elif event.type == pygame.MOUSEBUTTONDOWN and state == "playing":

                mouse_x, mouse_y = event.pos

                for button in buttons:
                    if button["rect"].collidepoint(mouse_x, mouse_y):
                        if button["label"] == "Rectángulo":
                            final_metric += 1

                        current_round += 1

                        if current_round >= rounds:
                            save_result_json(
                                patient_id,
                                test_key,
                                final_metric,
                                final_unit,
                                attempts
                            )
                            state = "result"
                        else:
                            generate_round()

        if state == "intro":
            draw_intro()
        elif state == "playing":
            draw_playing()
        elif state == "result":
            draw_result()

        pygame.display.flip()
        clock.tick(60)

    pygame.quit()

def run_acinetopsia_test(patient_id: str, test_key: str, test_name: str):
    
    pygame.init()

    width, height = 1200, 750
    screen = pygame.display.set_mode((width, height))
    pygame.display.set_caption(f"{APP_TITLE} - {test_name}")

    clock = pygame.time.Clock()

    title_font = pygame.font.SysFont("arial", 34, bold=True)
    font = pygame.font.SysFont("arial", 24)

    state = "intro"
    attempts = 1
    final_metric = 0
    final_unit = "objetos_capturados"

    duration_seconds = 25
    start_ticks = None

    targets = []

    for _ in range(8):
        targets.append({
            "x": random.randint(50, 300),
            "y": random.randint(140, height - 70),
            "r": random.randint(20, 30),
            "speed": random.randint(3, 7),
            "active": True
        })

    def draw_intro():
        screen.fill((18, 24, 32))

        t1 = title_font.render(test_name, True, (240, 240, 240))
        t2 = font.render("Capturá con click los objetos que cruzan la pantalla.", True, (220, 220, 220))
        t3 = font.render("Presioná ESPACIO para comenzar.", True, (120, 255, 180))

        screen.blit(t1, (60, 70))
        screen.blit(t2, (60, 210))
        screen.blit(t3, (60, 290))

    def draw_playing():
        screen.fill((240, 240, 240))

        elapsed = (pygame.time.get_ticks() - start_ticks) / 1000
        remaining = max(0, duration_seconds - elapsed)

        pygame.draw.rect(screen, (30, 30, 30), pygame.Rect(0, 0, width, 90))
        h1 = font.render(f"Capturados: {final_metric}", True, (255, 255, 255))
        h2 = font.render(f"Tiempo restante: {remaining:0.1f}s", True, (255, 230, 120))
        screen.blit(h1, (20, 18))
        screen.blit(h2, (20, 52))

        for target in targets:
            if target["active"]:
                pygame.draw.circle(screen, (60, 140, 255), (int(target["x"]), int(target["y"])), target["r"])
                pygame.draw.circle(screen, (20, 20, 20), (int(target["x"]), int(target["y"])), target["r"], 2)

    def draw_result():
        screen.fill((18, 24, 32))

        t1 = title_font.render("Resultado guardado", True, (220, 255, 220))
        t2 = font.render(f"Métrica principal: {final_metric} {final_unit}", True, (240, 240, 240))
        t3 = font.render("Presioná ENTER o ESC para volver.", True, (255, 220, 120))

        screen.blit(t1, (60, 100))
        screen.blit(t2, (60, 200))
        screen.blit(t3, (60, 280))

    running = True

    while running:
        for event in pygame.event.get():

            if event.type == pygame.QUIT:
                running = False

            elif event.type == pygame.KEYDOWN:

                if event.key == pygame.K_ESCAPE:
                    running = False

                elif state == "intro" and event.key == pygame.K_SPACE:
                    state = "playing"
                    start_ticks = pygame.time.get_ticks()

                elif state == "result" and event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                    running = False

            elif event.type == pygame.MOUSEBUTTONDOWN and state == "playing":

                mouse_x, mouse_y = event.pos

                for target in targets:
                    if not target["active"]:
                        continue

                    dx = mouse_x - target["x"]
                    dy = mouse_y - target["y"]
                    inside = (dx * dx + dy * dy) <= (target["r"] * target["r"])

                    if inside:
                        target["active"] = False
                        final_metric += 1
                        break

        if state == "playing":

            for target in targets:
                if target["active"]:
                    target["x"] += target["speed"]
                    if target["x"] > width + 30:
                        target["x"] = -30
                        target["y"] = random.randint(140, height - 70)

            elapsed = (pygame.time.get_ticks() - start_ticks) / 1000
            if elapsed >= duration_seconds:
                save_result_json(
                    patient_id,
                    test_key,
                    final_metric,
                    final_unit,
                    attempts
                )
                state = "result"

        if state == "intro":
            draw_intro()
        elif state == "playing":
            draw_playing()
        elif state == "result":
            draw_result()

        pygame.display.flip()
        clock.tick(60)

    pygame.quit()

def run_estabilizador_trayectoria_test(patient_id: str, test_key: str, test_name: str):
    pygame.init()

    width, height = 1200, 750
    screen = pygame.display.set_mode((width, height))
    pygame.display.set_caption(f"{APP_TITLE} - {test_name}")
    clock = pygame.time.Clock()

    title_font = pygame.font.SysFont("arial", 34, bold=True)
    font = pygame.font.SysFont("arial", 24)
    small_font = pygame.font.SysFont("arial", 20)

    state = "intro"
    attempts = 1
    final_metric = 0
    final_unit = "desvios"

    corridor_top = 280
    corridor_height = 140
    start_x = 100
    finish_x = 1050

    player_x = start_x
    player_y = corridor_top + corridor_height // 2
    player_radius = 14
    speed = 4

    deviations = 0
    finished = False

    def draw_intro():
        screen.fill((18, 24, 32))
        screen.blit(title_font.render(test_name, True, (240, 240, 240)), (60, 80))
        screen.blit(font.render("Llevá el cursor por el camino sin tocar los bordes.", True, (220, 220, 220)), (60, 210))
        screen.blit(font.render("Usá las flechas para avanzar.", True, (220, 220, 220)), (60, 255))
        screen.blit(font.render("Presioná ESPACIO para comenzar.", True, (120, 255, 180)), (60, 330))

    def draw_playing():
        screen.fill((240, 240, 240))
        pygame.draw.rect(screen, (30, 30, 30), pygame.Rect(0, 0, width, 90))
        screen.blit(font.render(f"Desvíos: {deviations}", True, (255, 255, 255)), (20, 22))
        screen.blit(small_font.render("Objetivo: llegar al final sin salir del carril", True, (255, 230, 120)), (20, 55))

        pygame.draw.rect(screen, (180, 220, 255), pygame.Rect(start_x, corridor_top, finish_x - start_x, corridor_height), border_radius=20)
        pygame.draw.rect(screen, (70, 100, 140), pygame.Rect(start_x, corridor_top, finish_x - start_x, corridor_height), 4, border_radius=20)

        pygame.draw.line(screen, (60, 180, 90), (finish_x, corridor_top - 20), (finish_x, corridor_top + corridor_height + 20), 6)

        pygame.draw.circle(screen, (72, 211, 154), (int(player_x), int(player_y)), player_radius)
        pygame.draw.circle(screen, (20, 20, 20), (int(player_x), int(player_y)), player_radius, 2)

    def draw_result():
        screen.fill((18, 24, 32))
        screen.blit(title_font.render("Resultado guardado", True, (220, 255, 220)), (60, 90))
        screen.blit(font.render(f"Métrica principal: {final_metric} {final_unit}", True, (240, 240, 240)), (60, 200))
        screen.blit(font.render("ENTER o ESC para volver.", True, (255, 220, 120)), (60, 280))

    running = True
    prev_inside = True

    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False

                elif state == "intro" and event.key == pygame.K_SPACE:
                    state = "playing"

                elif state == "result" and event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                    running = False

        if state == "playing":
            keys = pygame.key.get_pressed()

            if keys[pygame.K_RIGHT]:
                player_x += speed
            if keys[pygame.K_LEFT]:
                player_x -= speed
            if keys[pygame.K_UP]:
                player_y -= speed
            if keys[pygame.K_DOWN]:
                player_y += speed

            inside = (
                start_x <= player_x <= finish_x and
                corridor_top <= player_y <= corridor_top + corridor_height
            )

            if not inside and prev_inside:
                deviations += 1
            prev_inside = inside

            player_x = max(40, min(width - 40, player_x))
            player_y = max(120, min(height - 40, player_y))

            if player_x >= finish_x:
                final_metric = deviations
                save_result_json(patient_id, test_key, final_metric, final_unit, attempts)
                state = "result"

        if state == "intro":
            draw_intro()
        elif state == "playing":
            draw_playing()
        elif state == "result":
            draw_result()

        pygame.display.flip()
        clock.tick(60)

    pygame.quit()

def run_ley_de_fitts_test(patient_id: str, test_key: str, test_name: str):
    pygame.init()

    width, height = 1200, 750
    screen = pygame.display.set_mode((width, height))
    pygame.display.set_caption(f"{APP_TITLE} - {test_name}")
    clock = pygame.time.Clock()

    title_font = pygame.font.SysFont("arial", 34, bold=True)
    font = pygame.font.SysFont("arial", 24)

    state = "intro"
    attempts = 1
    final_metric = 0
    final_unit = "aciertos"

    trials = 10
    current_trial = 0
    target = None
    hits = 0

    sizes = [60, 50, 40, 30, 24]
    positions = [
        (200, 200), (1000, 220), (250, 500), (930, 540),
        (600, 220), (600, 540), (320, 340), (880, 350)
    ]

    def new_target():
        nonlocal target
        size = random.choice(sizes)
        x, y = random.choice(positions)
        target = pygame.Rect(x - size // 2, y - size // 2, size, size)

    new_target()

    def draw_intro():
        screen.fill((18, 24, 32))
        screen.blit(title_font.render(test_name, True, (240, 240, 240)), (60, 80))
        screen.blit(font.render("Tocá los objetivos lo más rápido y preciso posible.", True, (220, 220, 220)), (60, 210))
        screen.blit(font.render("Van a cambiar de tamaño y posición.", True, (220, 220, 220)), (60, 255))
        screen.blit(font.render("Presioná ESPACIO para comenzar.", True, (120, 255, 180)), (60, 330))

    def draw_playing():
        screen.fill((245, 245, 245))
        pygame.draw.rect(screen, (30, 30, 30), pygame.Rect(0, 0, width, 90))
        screen.blit(font.render(f"Intento {current_trial + 1}/{trials}", True, (255, 255, 255)), (20, 22))
        screen.blit(font.render(f"Aciertos: {hits}", True, (255, 230, 120)), (20, 55))

        pygame.draw.ellipse(screen, (72, 211, 154), target)
        pygame.draw.ellipse(screen, (20, 20, 20), target, 3)

    def draw_result():
        screen.fill((18, 24, 32))
        screen.blit(title_font.render("Resultado guardado", True, (220, 255, 220)), (60, 90))
        screen.blit(font.render(f"Métrica principal: {final_metric} {final_unit}", True, (240, 240, 240)), (60, 200))
        screen.blit(font.render("ENTER o ESC para volver.", True, (255, 220, 120)), (60, 280))

    running = True

    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif state == "intro" and event.key == pygame.K_SPACE:
                    state = "playing"
                elif state == "result" and event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                    running = False

            elif event.type == pygame.MOUSEBUTTONDOWN and state == "playing":
                if target.collidepoint(event.pos):
                    hits += 1

                current_trial += 1

                if current_trial >= trials:
                    final_metric = hits
                    save_result_json(patient_id, test_key, final_metric, final_unit, attempts)
                    state = "result"
                else:
                    new_target()

        if state == "intro":
            draw_intro()
        elif state == "playing":
            draw_playing()
        elif state == "result":
            draw_result()

        pygame.display.flip()
        clock.tick(60)

    pygame.quit()

def run_barrido_ritmico_test(patient_id: str, test_key: str, test_name: str):
    pygame.init()

    width, height = 1200, 750
    screen = pygame.display.set_mode((width, height))
    pygame.display.set_caption(f"{APP_TITLE} - {test_name}")
    clock = pygame.time.Clock()

    title_font = pygame.font.SysFont("arial", 34, bold=True)
    font = pygame.font.SysFont("arial", 24)

    state = "intro"
    attempts = 1
    final_metric = 0
    final_unit = "selecciones_correctas"

    options = ["A", "B", "C", "D"]
    target_option = "C"
    current_index = 0
    last_switch = 0
    switch_interval = 700
    total_rounds = 8
    current_round = 0
    correct = 0

    def draw_intro():
        screen.fill((18, 24, 32))
        screen.blit(title_font.render(test_name, True, (240, 240, 240)), (60, 80))
        screen.blit(font.render("El selector recorre opciones automáticamente.", True, (220, 220, 220)), (60, 210))
        screen.blit(font.render("Presioná ESPACIO cuando esté sobre la opción objetivo.", True, (220, 220, 220)), (60, 255))
        screen.blit(font.render(f"Objetivo actual: {target_option}", True, (255, 230, 120)), (60, 300))
        screen.blit(font.render("Presioná ENTER para comenzar.", True, (120, 255, 180)), (60, 355))

    def draw_playing():
        screen.fill((245, 245, 245))
        pygame.draw.rect(screen, (30, 30, 30), pygame.Rect(0, 0, width, 90))
        screen.blit(font.render(f"Ronda {current_round + 1}/{total_rounds}", True, (255, 255, 255)), (20, 22))
        screen.blit(font.render(f"Aciertos: {correct}", True, (255, 230, 120)), (20, 55))

        start_x = 220
        for i, option in enumerate(options):
            rect = pygame.Rect(start_x + i * 180, 300, 120, 120)
            color = (72, 211, 154) if i == current_index else (200, 210, 220)
            pygame.draw.rect(screen, color, rect, border_radius=16)
            pygame.draw.rect(screen, (20, 20, 20), rect, 3, border_radius=16)
            txt = title_font.render(option, True, (20, 20, 20))
            screen.blit(txt, (rect.x + 38, rect.y + 28))

        screen.blit(font.render(f"Objetivo: {target_option}", True, (20, 20, 20)), (500, 500))

    def draw_result():
        screen.fill((18, 24, 32))
        screen.blit(title_font.render("Resultado guardado", True, (220, 255, 220)), (60, 90))
        screen.blit(font.render(f"Métrica principal: {final_metric} {final_unit}", True, (240, 240, 240)), (60, 200))
        screen.blit(font.render("ENTER o ESC para volver.", True, (255, 220, 120)), (60, 280))

    running = True

    while running:
        now = pygame.time.get_ticks()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False

                elif state == "intro" and event.key == pygame.K_RETURN:
                    state = "playing"
                    last_switch = now

                elif state == "playing" and event.key == pygame.K_SPACE:
                    if options[current_index] == target_option:
                        correct += 1

                    current_round += 1

                    if current_round >= total_rounds:
                        final_metric = correct
                        save_result_json(patient_id, test_key, final_metric, final_unit, attempts)
                        state = "result"
                    else:
                        target_option = random.choice(options)

                elif state == "result" and event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                    running = False

        if state == "playing":
            if now - last_switch >= switch_interval:
                current_index = (current_index + 1) % len(options)
                last_switch = now

        if state == "intro":
            draw_intro()
        elif state == "playing":
            draw_playing()
        elif state == "result":
            draw_result()

        pygame.display.flip()
        clock.tick(60)

    pygame.quit()

def run_arrastre_sostenido_test(patient_id: str, test_key: str, test_name: str):
    pygame.init()

    width, height = 1200, 750
    screen = pygame.display.set_mode((width, height))
    pygame.display.set_caption(f"{APP_TITLE} - {test_name}")
    clock = pygame.time.Clock()

    title_font = pygame.font.SysFont("arial", 34, bold=True)
    font = pygame.font.SysFont("arial", 24)

    state = "intro"
    attempts = 1
    final_metric = 0
    final_unit = "arrastres_correctos"

    obj_rect = pygame.Rect(180, 320, 90, 90)
    target_rect = pygame.Rect(920, 300, 140, 140)
    dragging = False
    offset_x = 0
    offset_y = 0
    completed = 0
    total_rounds = 5
    round_count = 0

    def reset_object():
        obj_rect.x = 180
        obj_rect.y = 320

    def draw_intro():
        screen.fill((18, 24, 32))
        screen.blit(title_font.render(test_name, True, (240, 240, 240)), (60, 80))
        screen.blit(font.render("Arrastrá el objeto hasta el área objetivo sin soltarlo.", True, (220, 220, 220)), (60, 210))
        screen.blit(font.render("Presioná ESPACIO para comenzar.", True, (120, 255, 180)), (60, 300))

    def draw_playing():
        screen.fill((245, 245, 245))
        pygame.draw.rect(screen, (30, 30, 30), pygame.Rect(0, 0, width, 90))
        screen.blit(font.render(f"Ronda {round_count + 1}/{total_rounds}", True, (255, 255, 255)), (20, 22))
        screen.blit(font.render(f"Completados: {completed}", True, (255, 230, 120)), (20, 55))

        pygame.draw.rect(screen, (180, 220, 255), target_rect, border_radius=18)
        pygame.draw.rect(screen, (60, 120, 170), target_rect, 4, border_radius=18)

        pygame.draw.rect(screen, (72, 211, 154), obj_rect, border_radius=14)
        pygame.draw.rect(screen, (20, 20, 20), obj_rect, 3, border_radius=14)

    def draw_result():
        screen.fill((18, 24, 32))
        screen.blit(title_font.render("Resultado guardado", True, (220, 255, 220)), (60, 90))
        screen.blit(font.render(f"Métrica principal: {final_metric} {final_unit}", True, (240, 240, 240)), (60, 200))
        screen.blit(font.render("ENTER o ESC para volver.", True, (255, 220, 120)), (60, 280))

    running = True

    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif state == "intro" and event.key == pygame.K_SPACE:
                    state = "playing"
                elif state == "result" and event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                    running = False

            elif event.type == pygame.MOUSEBUTTONDOWN and state == "playing":
                if obj_rect.collidepoint(event.pos):
                    dragging = True
                    offset_x = obj_rect.x - event.pos[0]
                    offset_y = obj_rect.y - event.pos[1]

            elif event.type == pygame.MOUSEBUTTONUP and state == "playing":
                if dragging:
                    dragging = False
                    if target_rect.colliderect(obj_rect):
                        completed += 1
                    round_count += 1

                    if round_count >= total_rounds:
                        final_metric = completed
                        save_result_json(patient_id, test_key, final_metric, final_unit, attempts)
                        state = "result"
                    else:
                        reset_object()

            elif event.type == pygame.MOUSEMOTION and state == "playing" and dragging:
                obj_rect.x = event.pos[0] + offset_x
                obj_rect.y = event.pos[1] + offset_y

        if state == "intro":
            draw_intro()
        elif state == "playing":
            draw_playing()
        elif state == "result":
            draw_result()

        pygame.display.flip()
        clock.tick(60)

    pygame.quit()

def run_ganancia_adaptativa_test(patient_id: str, test_key: str, test_name: str):
    pygame.init()

    width, height = 1200, 750
    screen = pygame.display.set_mode((width, height))
    pygame.display.set_caption(f"{APP_TITLE} - {test_name}")
    clock = pygame.time.Clock()

    title_font = pygame.font.SysFont("arial", 34, bold=True)
    font = pygame.font.SysFont("arial", 24)
    small_font = pygame.font.SysFont("arial", 20)

    state = "intro"
    attempts = 1
    final_metric = 0
    final_unit = "objetivos_alcanzados"

    cursor_x, cursor_y = 150, 375
    gain = 1.8
    speed = 3
    hits = 0
    total_targets = 6
    target_index = 0

    targets = [
        pygame.Rect(920, 140, 70, 70),
        pygame.Rect(800, 250, 70, 70),
        pygame.Rect(980, 340, 70, 70),
        pygame.Rect(760, 450, 70, 70),
        pygame.Rect(930, 560, 70, 70),
        pygame.Rect(840, 640, 70, 70),
    ]

    def draw_intro():
        screen.fill((18, 24, 32))
        screen.blit(title_font.render(test_name, True, (240, 240, 240)), (60, 80))
        screen.blit(font.render("Mové el cursor adaptado hasta alcanzar los objetivos.", True, (220, 220, 220)), (60, 210))
        screen.blit(font.render("La sensibilidad está aumentada para reducir el recorrido.", True, (220, 220, 220)), (60, 255))
        screen.blit(font.render("Usá flechas y presioná ESPACIO para comenzar.", True, (120, 255, 180)), (60, 330))

    def draw_playing():
        screen.fill((245, 245, 245))
        pygame.draw.rect(screen, (30, 30, 30), pygame.Rect(0, 0, width, 90))
        screen.blit(font.render(f"Objetivo {target_index + 1}/{total_targets}", True, (255, 255, 255)), (20, 22))
        screen.blit(small_font.render(f"Aciertos: {hits}   |   Ganancia: x{gain}", True, (255, 230, 120)), (20, 55))

        for i, rect in enumerate(targets):
            color = (72, 211, 154) if i == target_index else (180, 220, 255)
            pygame.draw.rect(screen, color, rect, border_radius=16)
            pygame.draw.rect(screen, (20, 20, 20), rect, 3, border_radius=16)

        pygame.draw.circle(screen, (255, 120, 120), (int(cursor_x), int(cursor_y)), 15)
        pygame.draw.circle(screen, (20, 20, 20), (int(cursor_x), int(cursor_y)), 15, 2)

    def draw_result():
        screen.fill((18, 24, 32))
        screen.blit(title_font.render("Resultado guardado", True, (220, 255, 220)), (60, 90))
        screen.blit(font.render(f"Métrica principal: {final_metric} {final_unit}", True, (240, 240, 240)), (60, 200))
        screen.blit(font.render("ENTER o ESC para volver.", True, (255, 220, 120)), (60, 280))

    running = True

    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False

                elif state == "intro" and event.key == pygame.K_SPACE:
                    state = "playing"

                elif state == "result" and event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                    running = False

        if state == "playing":
            keys = pygame.key.get_pressed()
            if keys[pygame.K_RIGHT]:
                cursor_x += speed * gain
            if keys[pygame.K_LEFT]:
                cursor_x -= speed * gain
            if keys[pygame.K_UP]:
                cursor_y -= speed * gain
            if keys[pygame.K_DOWN]:
                cursor_y += speed * gain

            cursor_x = max(30, min(width - 30, cursor_x))
            cursor_y = max(120, min(height - 30, cursor_y))

            if targets[target_index].collidepoint(cursor_x, cursor_y):
                hits += 1
                target_index += 1

                if target_index >= total_targets:
                    final_metric = hits
                    save_result_json(patient_id, test_key, final_metric, final_unit, attempts)
                    state = "result"

        if state == "intro":
            draw_intro()
        elif state == "playing":
            draw_playing()
        elif state == "result":
            draw_result()

        pygame.display.flip()
        clock.tick(60)

    pygame.quit()

def run_reaccion_multimodal_test(patient_id: str, test_key: str, test_name: str):
    pygame.init()
    pygame.mixer.init()

    width, height = 1200, 750
    screen = pygame.display.set_mode((width, height))
    pygame.display.set_caption(f"{APP_TITLE} - {test_name}")
    clock = pygame.time.Clock()

    title_font = pygame.font.SysFont("arial", 34, bold=True)
    font = pygame.font.SysFont("arial", 24)

    state = "intro"
    attempts = 1
    final_metric = 0
    final_unit = "respuestas_correctas"

    total_trials = 8
    current_trial = 0
    correct = 0
    current_mode = None
    visual_active = False
    visual_rect = pygame.Rect(530, 280, 140, 140)

    def play_beep():
        try:
            sample_rate = 22050
            duration = 0.18
            frequency = 880
            n_samples = int(sample_rate * duration)
            import array, math
            buf = array.array("h")
            amplitude = 16000
            for s in range(n_samples):
                t = float(s) / sample_rate
                buf.append(int(amplitude * math.sin(2 * math.pi * frequency * t)))
            sound = pygame.mixer.Sound(buffer=buf)
            sound.play()
        except Exception:
            pass

    def next_trial():
        nonlocal current_mode, visual_active
        current_mode = random.choice(["visual", "audio"])
        visual_active = current_mode == "visual"
        if current_mode == "audio":
            play_beep()

    next_trial()

    def draw_intro():
        screen.fill((18, 24, 32))
        screen.blit(title_font.render(test_name, True, (240, 240, 240)), (60, 80))
        screen.blit(font.render("Respondé a estímulos visuales y auditivos.", True, (220, 220, 220)), (60, 210))
        screen.blit(font.render("Click para estímulo visual, B para estímulo auditivo.", True, (220, 220, 220)), (60, 255))
        screen.blit(font.render("Presioná ESPACIO para comenzar.", True, (120, 255, 180)), (60, 330))

    def draw_playing():
        screen.fill((245, 245, 245))
        pygame.draw.rect(screen, (30, 30, 30), pygame.Rect(0, 0, width, 90))
        screen.blit(font.render(f"Intento {current_trial + 1}/{total_trials}", True, (255, 255, 255)), (20, 22))
        screen.blit(font.render(f"Correctas: {correct}", True, (255, 230, 120)), (20, 55))

        if visual_active:
            pygame.draw.rect(screen, (72, 211, 154), visual_rect, border_radius=20)
            pygame.draw.rect(screen, (20, 20, 20), visual_rect, 3, border_radius=20)
        else:
            screen.blit(font.render("Escuchá el estímulo y respondé con la tecla B", True, (20, 20, 20)), (350, 340))

    def draw_result():
        screen.fill((18, 24, 32))
        screen.blit(title_font.render("Resultado guardado", True, (220, 255, 220)), (60, 90))
        screen.blit(font.render(f"Métrica principal: {final_metric} {final_unit}", True, (240, 240, 240)), (60, 200))
        screen.blit(font.render("ENTER o ESC para volver.", True, (255, 220, 120)), (60, 280))

    running = True

    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False

                elif state == "intro" and event.key == pygame.K_SPACE:
                    state = "playing"

                elif state == "playing" and event.key == pygame.K_b:
                    if current_mode == "audio":
                        correct += 1
                    current_trial += 1
                    if current_trial >= total_trials:
                        final_metric = correct
                        save_result_json(patient_id, test_key, final_metric, final_unit, attempts)
                        state = "result"
                    else:
                        next_trial()

                elif state == "result" and event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                    running = False

            elif event.type == pygame.MOUSEBUTTONDOWN and state == "playing":
                if visual_active and visual_rect.collidepoint(event.pos):
                    correct += 1

                if current_mode == "visual":
                    current_trial += 1
                    if current_trial >= total_trials:
                        final_metric = correct
                        save_result_json(patient_id, test_key, final_metric, final_unit, attempts)
                        state = "result"
                    else:
                        next_trial()

        if state == "intro":
            draw_intro()
        elif state == "playing":
            draw_playing()
        elif state == "result":
            draw_result()

        pygame.display.flip()
        clock.tick(60)

    pygame.quit()

def run_denominacion_fonologica_test(patient_id: str, test_key: str, test_name: str):
    pygame.init()

    width, height = 1200, 760
    screen = pygame.display.set_mode((width, height))
    pygame.display.set_caption(f"{APP_TITLE} - {test_name}")
    clock = pygame.time.Clock()

    title_font = pygame.font.SysFont("arial", 34, bold=True)
    font = pygame.font.SysFont("arial", 24)
    word_font = pygame.font.SysFont("arial", 30, bold=True)

    state = "intro"
    attempts = 1
    final_metric = 0
    final_unit = "respuestas_correctas"

    items = [
        {"object": "🦆", "correct": "Pato", "options": ["Pato", "Plato", "Gato"]},
        {"object": "🍞", "correct": "Pan", "options": ["Pan", "Pez", "Plan"]},
        {"object": "🐱", "correct": "Gato", "options": ["Gato", "Pato", "Dato"]},
        {"object": "☕", "correct": "Taza", "options": ["Taza", "Casa", "Masa"]},
        {"object": "🌞", "correct": "Sol", "options": ["Sol", "Sal", "Son"]},
    ]

    current_item = 0
    correct_count = 0
    option_buttons = []

    def build_option_buttons():
        nonlocal option_buttons
        option_buttons = []
        x_positions = [180, 460, 740]
        for i, option in enumerate(items[current_item]["options"]):
            rect = pygame.Rect(x_positions[i], 520, 220, 70)
            option_buttons.append({"label": option, "rect": rect})

    build_option_buttons()

    def draw_intro():
        screen.fill((18, 24, 32))
        screen.blit(title_font.render(test_name, True, (240, 240, 240)), (60, 80))
        screen.blit(font.render("Elegí el nombre correcto entre opciones parecidas.", True, (220, 220, 220)), (60, 220))
        screen.blit(font.render("Presioná ESPACIO para comenzar.", True, (120, 255, 180)), (60, 280))

    def draw_playing():
        screen.fill((245, 245, 245))
        pygame.draw.rect(screen, (30, 30, 30), pygame.Rect(0, 0, width, 90))
        screen.blit(font.render(f"Ítem {current_item + 1}/{len(items)}", True, (255, 255, 255)), (20, 30))

        emoji_text = title_font.render(items[current_item]["object"], True, (20, 20, 20))
        screen.blit(emoji_text, (565, 220))

        instruction = font.render("¿Cuál es el nombre correcto?", True, (30, 30, 30))
        screen.blit(instruction, (450, 360))

        for button in option_buttons:
            pygame.draw.rect(screen, (80, 170, 255), button["rect"], border_radius=12)
            pygame.draw.rect(screen, (20, 20, 20), button["rect"], 2, border_radius=12)
            txt = word_font.render(button["label"], True, (255, 255, 255))
            txt_rect = txt.get_rect(center=button["rect"].center)
            screen.blit(txt, txt_rect)

    def draw_result():
        screen.fill((18, 24, 32))
        screen.blit(title_font.render("Resultado guardado", True, (220, 255, 220)), (60, 100))
        screen.blit(font.render(f"Métrica principal: {final_metric} {final_unit}", True, (240, 240, 240)), (60, 200))
        screen.blit(font.render("ENTER o ESC para volver.", True, (255, 220, 120)), (60, 280))

    running = True

    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif state == "intro" and event.key == pygame.K_SPACE:
                    state = "playing"
                    current_item = 0
                    correct_count = 0
                    build_option_buttons()
                elif state == "result" and event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                    running = False

            elif event.type == pygame.MOUSEBUTTONDOWN and state == "playing":
                for button in option_buttons:
                    if button["rect"].collidepoint(event.pos):
                        if button["label"] == items[current_item]["correct"]:
                            correct_count += 1

                        current_item += 1

                        if current_item >= len(items):
                            final_metric = correct_count
                            save_result_json(patient_id, test_key, final_metric, final_unit, attempts)
                            state = "result"
                        else:
                            build_option_buttons()
                        break

        if state == "intro":
            draw_intro()
        elif state == "playing":
            draw_playing()
        else:
            draw_result()

        pygame.display.flip()
        clock.tick(60)

    pygame.quit()


def run_memoria_n_back_test(patient_id: str, test_key: str, test_name: str):
    pygame.init()

    width, height = 1200, 760
    screen = pygame.display.set_mode((width, height))
    pygame.display.set_caption(f"{APP_TITLE} - {test_name}")
    clock = pygame.time.Clock()

    title_font = pygame.font.SysFont("arial", 34, bold=True)
    font = pygame.font.SysFont("arial", 24)
    big_font = pygame.font.SysFont("arial", 80, bold=True)

    state = "intro"
    attempts = 1
    final_metric = 0
    final_unit = "aciertos"

    n_value = 2
    sequence = ["▲", "■", "▲", "●", "■", "■", "●", "▲"]
    current_index = 0
    correct_count = 0
    total_matches = 0
    showing_item = False
    item_start = 0
    item_duration = 1200
    pause_duration = 600
    response_registered = False

    for i in range(n_value, len(sequence)):
        if sequence[i] == sequence[i - n_value]:
            total_matches += 1

    def draw_intro():
        screen.fill((18, 24, 32))
        screen.blit(title_font.render(test_name, True, (240, 240, 240)), (60, 80))
        screen.blit(font.render(f"Presioná ESPACIO si la figura actual coincide con la de hace {n_value} pasos.", True, (220, 220, 220)), (60, 220))
        screen.blit(font.render("Presioná ENTER para comenzar.", True, (120, 255, 180)), (60, 280))

    def draw_playing():
        screen.fill((245, 245, 245))
        pygame.draw.rect(screen, (30, 30, 30), pygame.Rect(0, 0, width, 90))
        screen.blit(font.render(f"Secuencia {current_index + 1}/{len(sequence)}", True, (255, 255, 255)), (20, 30))
        screen.blit(font.render(f"N = {n_value}", True, (255, 230, 120)), (1080, 30))

        if showing_item and current_index < len(sequence):
            txt = big_font.render(sequence[current_index], True, (30, 30, 30))
            txt_rect = txt.get_rect(center=(width // 2, height // 2))
            screen.blit(txt, txt_rect)

    def draw_result():
        screen.fill((18, 24, 32))
        screen.blit(title_font.render("Resultado guardado", True, (220, 255, 220)), (60, 100))
        screen.blit(font.render(f"Métrica principal: {final_metric} {final_unit}", True, (240, 240, 240)), (60, 200))
        screen.blit(font.render(f"Coincidencias reales en la secuencia: {total_matches}", True, (240, 240, 240)), (60, 250))
        screen.blit(font.render("ENTER o ESC para volver.", True, (255, 220, 120)), (60, 320))

    running = True

    while running:
        now = pygame.time.get_ticks()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif state == "intro" and event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                    state = "playing"
                    current_index = 0
                    correct_count = 0
                    showing_item = True
                    item_start = now
                    response_registered = False
                elif state == "playing" and event.key == pygame.K_SPACE:
                    if showing_item and not response_registered and current_index >= n_value:
                        if sequence[current_index] == sequence[current_index - n_value]:
                            correct_count += 1
                        response_registered = True
                elif state == "result" and event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                    running = False

        if state == "playing":
            if showing_item:
                if now - item_start >= item_duration:
                    showing_item = False
                    item_start = now
            else:
                if now - item_start >= pause_duration:
                    current_index += 1
                    if current_index >= len(sequence):
                        final_metric = correct_count
                        save_result_json(patient_id, test_key, final_metric, final_unit, attempts)
                        state = "result"
                    else:
                        showing_item = True
                        item_start = now
                        response_registered = False

        if state == "intro":
            draw_intro()
        elif state == "playing":
            draw_playing()
        else:
            draw_result()

        pygame.display.flip()
        clock.tick(60)

    pygame.quit()


def run_efecto_stroop_test(patient_id: str, test_key: str, test_name: str):
    pygame.init()

    width, height = 1200, 760
    screen = pygame.display.set_mode((width, height))
    pygame.display.set_caption(f"{APP_TITLE} - {test_name}")
    clock = pygame.time.Clock()

    title_font = pygame.font.SysFont("arial", 34, bold=True)
    font = pygame.font.SysFont("arial", 24)
    word_font = pygame.font.SysFont("arial", 60, bold=True)

    state = "intro"
    attempts = 1
    final_metric = 0
    final_unit = "aciertos"

    colors = {
        "ROJO": (220, 60, 60),
        "AZUL": (70, 120, 240),
        "VERDE": (70, 180, 90),
        "AMARILLO": (220, 190, 50)
    }

    trials = [
        {"word": "ROJO", "ink": "AZUL"},
        {"word": "AZUL", "ink": "VERDE"},
        {"word": "VERDE", "ink": "ROJO"},
        {"word": "AMARILLO", "ink": "AZUL"},
        {"word": "ROJO", "ink": "VERDE"},
    ]

    buttons = []
    current_trial = 0
    correct_count = 0

    def build_buttons():
        nonlocal buttons
        labels = ["ROJO", "AZUL", "VERDE", "AMARILLO"]
        buttons = []
        x_positions = [120, 390, 660, 930]
        for i, label in enumerate(labels):
            rect = pygame.Rect(x_positions[i], 560, 170, 65)
            buttons.append({"label": label, "rect": rect})

    build_buttons()

    def draw_intro():
        screen.fill((18, 24, 32))
        screen.blit(title_font.render(test_name, True, (240, 240, 240)), (60, 80))
        screen.blit(font.render("Elegí el color de la tinta, ignorando la palabra escrita.", True, (220, 220, 220)), (60, 220))
        screen.blit(font.render("Presioná ESPACIO para comenzar.", True, (120, 255, 180)), (60, 280))

    def draw_playing():
        screen.fill((245, 245, 245))
        pygame.draw.rect(screen, (30, 30, 30), pygame.Rect(0, 0, width, 90))
        screen.blit(font.render(f"Ítem {current_trial + 1}/{len(trials)}", True, (255, 255, 255)), (20, 30))

        current = trials[current_trial]
        txt = word_font.render(current["word"], True, colors[current["ink"]])
        txt_rect = txt.get_rect(center=(width // 2, 280))
        screen.blit(txt, txt_rect)

        for button in buttons:
            pygame.draw.rect(screen, colors[button["label"]], button["rect"], border_radius=12)
            pygame.draw.rect(screen, (20, 20, 20), button["rect"], 2, border_radius=12)
            btn_txt = font.render(button["label"], True, (255, 255, 255))
            btn_rect = btn_txt.get_rect(center=button["rect"].center)
            screen.blit(btn_txt, btn_rect)

    def draw_result():
        screen.fill((18, 24, 32))
        screen.blit(title_font.render("Resultado guardado", True, (220, 255, 220)), (60, 100))
        screen.blit(font.render(f"Métrica principal: {final_metric} {final_unit}", True, (240, 240, 240)), (60, 200))
        screen.blit(font.render("ENTER o ESC para volver.", True, (255, 220, 120)), (60, 280))

    running = True

    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif state == "intro" and event.key == pygame.K_SPACE:
                    state = "playing"
                    current_trial = 0
                    correct_count = 0
                elif state == "result" and event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                    running = False

            elif event.type == pygame.MOUSEBUTTONDOWN and state == "playing":
                for button in buttons:
                    if button["rect"].collidepoint(event.pos):
                        if button["label"] == trials[current_trial]["ink"]:
                            correct_count += 1

                        current_trial += 1

                        if current_trial >= len(trials):
                            final_metric = correct_count
                            save_result_json(patient_id, test_key, final_metric, final_unit, attempts)
                            state = "result"
                        break

        if state == "intro":
            draw_intro()
        elif state == "playing":
            draw_playing()
        else:
            draw_result()

        pygame.display.flip()
        clock.tick(60)

    pygame.quit()


def run_completamiento_semantico_test(patient_id: str, test_key: str, test_name: str):
    pygame.init()

    width, height = 1200, 760
    screen = pygame.display.set_mode((width, height))
    pygame.display.set_caption(f"{APP_TITLE} - {test_name}")
    clock = pygame.time.Clock()

    title_font = pygame.font.SysFont("arial", 34, bold=True)
    font = pygame.font.SysFont("arial", 24)

    state = "intro"
    attempts = 1
    final_metric = 0
    final_unit = "respuestas_correctas"

    items = [
        {"emoji": "🦷", "sentence": "Para lavarse los dientes se usa un ____.", "correct": "cepillo", "options": ["cepillo", "tenedor", "martillo"]},
        {"emoji": "☔", "sentence": "Cuando llueve, conviene llevar ____.", "correct": "paraguas", "options": ["paraguas", "almohada", "cuchara"]},
        {"emoji": "🍽️", "sentence": "Para comer sopa se usa una ____.", "correct": "cuchara", "options": ["cuchara", "raqueta", "pelota"]},
        {"emoji": "🛏️", "sentence": "Antes de dormir, una persona suele acostarse en la ____.", "correct": "cama", "options": ["cama", "heladera", "bicicleta"]},
    ]

    current_item = 0
    correct_count = 0
    buttons = []

    def build_buttons():
        nonlocal buttons
        buttons = []
        x_positions = [150, 450, 750]
        for i, option in enumerate(items[current_item]["options"]):
            rect = pygame.Rect(x_positions[i], 540, 220, 65)
            buttons.append({"label": option, "rect": rect})

    build_buttons()

    def draw_intro():
        screen.fill((18, 24, 32))
        screen.blit(title_font.render(test_name, True, (240, 240, 240)), (60, 80))
        screen.blit(font.render("Elegí la palabra que completa correctamente la oración.", True, (220, 220, 220)), (60, 220))
        screen.blit(font.render("Presioná ESPACIO para comenzar.", True, (120, 255, 180)), (60, 280))

    def draw_playing():
        screen.fill((245, 245, 245))
        pygame.draw.rect(screen, (30, 30, 30), pygame.Rect(0, 0, width, 90))
        screen.blit(font.render(f"Ítem {current_item + 1}/{len(items)}", True, (255, 255, 255)), (20, 30))

        emoji = title_font.render(items[current_item]["emoji"], True, (30, 30, 30))
        screen.blit(emoji, (565, 180))

        sentence = font.render(items[current_item]["sentence"], True, (30, 30, 30))
        sentence_rect = sentence.get_rect(center=(width // 2, 340))
        screen.blit(sentence, sentence_rect)

        for button in buttons:
            pygame.draw.rect(screen, (80, 170, 255), button["rect"], border_radius=12)
            pygame.draw.rect(screen, (20, 20, 20), button["rect"], 2, border_radius=12)
            txt = font.render(button["label"], True, (255, 255, 255))
            txt_rect = txt.get_rect(center=button["rect"].center)
            screen.blit(txt, txt_rect)

    def draw_result():
        screen.fill((18, 24, 32))
        screen.blit(title_font.render("Resultado guardado", True, (220, 255, 220)), (60, 100))
        screen.blit(font.render(f"Métrica principal: {final_metric} {final_unit}", True, (240, 240, 240)), (60, 200))
        screen.blit(font.render("ENTER o ESC para volver.", True, (255, 220, 120)), (60, 280))

    running = True

    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif state == "intro" and event.key == pygame.K_SPACE:
                    state = "playing"
                    current_item = 0
                    correct_count = 0
                    build_buttons()
                elif state == "result" and event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                    running = False

            elif event.type == pygame.MOUSEBUTTONDOWN and state == "playing":
                for button in buttons:
                    if button["rect"].collidepoint(event.pos):
                        if button["label"] == items[current_item]["correct"]:
                            correct_count += 1

                        current_item += 1

                        if current_item >= len(items):
                            final_metric = correct_count
                            save_result_json(patient_id, test_key, final_metric, final_unit, attempts)
                            state = "result"
                        else:
                            build_buttons()
                        break

        if state == "intro":
            draw_intro()
        elif state == "playing":
            draw_playing()
        else:
            draw_result()

        pygame.display.flip()
        clock.tick(60)

    pygame.quit()


def run_intruso_logico_test(patient_id: str, test_key: str, test_name: str):
    pygame.init()

    width, height = 1200, 760
    screen = pygame.display.set_mode((width, height))
    pygame.display.set_caption(f"{APP_TITLE} - {test_name}")
    clock = pygame.time.Clock()

    title_font = pygame.font.SysFont("arial", 34, bold=True)
    font = pygame.font.SysFont("arial", 24)
    emoji_font = pygame.font.SysFont("arial", 58)

    state = "intro"
    attempts = 1
    final_metric = 0
    final_unit = "aciertos"

    groups = [
        {"items": ["🍎", "🍌", "🍐", "🚗"], "intruder": "🚗"},
        {"items": ["🐶", "🐱", "🐭", "🍞"], "intruder": "🍞"},
        {"items": ["🚌", "🚗", "🚲", "🌳"], "intruder": "🌳"},
        {"items": ["👕", "👖", "🧢", "⚽"], "intruder": "⚽"},
    ]

    current_group = 0
    correct_count = 0
    buttons = []

    def build_buttons():
        nonlocal buttons
        buttons = []
        x_positions = [150, 400, 650, 900]
        for i, item in enumerate(groups[current_group]["items"]):
            rect = pygame.Rect(x_positions[i], 360, 140, 120)
            buttons.append({"label": item, "rect": rect})

    build_buttons()

    def draw_intro():
        screen.fill((18, 24, 32))
        screen.blit(title_font.render(test_name, True, (240, 240, 240)), (60, 80))
        screen.blit(font.render("Elegí el elemento que no pertenece al grupo.", True, (220, 220, 220)), (60, 220))
        screen.blit(font.render("Presioná ESPACIO para comenzar.", True, (120, 255, 180)), (60, 280))

    def draw_playing():
        screen.fill((245, 245, 245))
        pygame.draw.rect(screen, (30, 30, 30), pygame.Rect(0, 0, width, 90))
        screen.blit(font.render(f"Grupo {current_group + 1}/{len(groups)}", True, (255, 255, 255)), (20, 30))

        instruction = font.render("¿Cuál es el intruso lógico?", True, (30, 30, 30))
        screen.blit(instruction, (455, 220))

        for button in buttons:
            pygame.draw.rect(screen, (80, 170, 255), button["rect"], border_radius=12)
            pygame.draw.rect(screen, (20, 20, 20), button["rect"], 2, border_radius=12)
            txt = emoji_font.render(button["label"], True, (255, 255, 255))
            txt_rect = txt.get_rect(center=button["rect"].center)
            screen.blit(txt, txt_rect)

    def draw_result():
        screen.fill((18, 24, 32))
        screen.blit(title_font.render("Resultado guardado", True, (220, 255, 220)), (60, 100))
        screen.blit(font.render(f"Métrica principal: {final_metric} {final_unit}", True, (240, 240, 240)), (60, 200))
        screen.blit(font.render("ENTER o ESC para volver.", True, (255, 220, 120)), (60, 280))

    running = True

    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif state == "intro" and event.key == pygame.K_SPACE:
                    state = "playing"
                    current_group = 0
                    correct_count = 0
                    build_buttons()
                elif state == "result" and event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                    running = False

            elif event.type == pygame.MOUSEBUTTONDOWN and state == "playing":
                for button in buttons:
                    if button["rect"].collidepoint(event.pos):
                        if button["label"] == groups[current_group]["intruder"]:
                            correct_count += 1

                        current_group += 1
                        if current_group >= len(groups):
                            final_metric = correct_count
                            save_result_json(patient_id, test_key, final_metric, final_unit, attempts)
                            state = "result"
                        else:
                            build_buttons()
                        break

        if state == "intro":
            draw_intro()
        elif state == "playing":
            draw_playing()
        else:
            draw_result()

        pygame.display.flip()
        clock.tick(60)

    pygame.quit()


def run_secuenciacion_avd_test(patient_id: str, test_key: str, test_name: str):
    pygame.init()

    width, height = 1200, 760
    screen = pygame.display.set_mode((width, height))
    pygame.display.set_caption(f"{APP_TITLE} - {test_name}")
    clock = pygame.time.Clock()

    title_font = pygame.font.SysFont("arial", 34, bold=True)
    font = pygame.font.SysFont("arial", 22)

    state = "intro"
    attempts = 1
    final_metric = 0
    final_unit = "secuencias_correctas"

    sequences = [
        {
            "title": "Lavarse las manos",
            "correct_order": [
                "Abrir la canilla",
                "Mojarse las manos",
                "Ponerse jabón",
                "Enjuagarse",
            ]
        },
        {
            "title": "Cepillarse los dientes",
            "correct_order": [
                "Poner pasta en el cepillo",
                "Cepillarse",
                "Enjuagarse la boca",
                "Guardar el cepillo",
            ]
        }
    ]

    current_sequence = 0
    selected_order = []
    correct_count = 0
    step_buttons = []

    def build_buttons():
        nonlocal step_buttons
        selected_order.clear()
        options = sequences[current_sequence]["correct_order"][:]
        random.shuffle(options)
        step_buttons = []

        y0 = 250
        for i, step in enumerate(options):
            rect = pygame.Rect(220, y0 + i * 90, 760, 65)
            step_buttons.append({"label": step, "rect": rect, "used": False})

    build_buttons()

    def draw_intro():
        screen.fill((18, 24, 32))
        screen.blit(title_font.render(test_name, True, (240, 240, 240)), (60, 80))
        screen.blit(font.render("Seleccioná los pasos en el orden correcto de la actividad.", True, (220, 220, 220)), (60, 220))
        screen.blit(font.render("Presioná ESPACIO para comenzar.", True, (120, 255, 180)), (60, 280))

    def draw_playing():
        screen.fill((245, 245, 245))
        pygame.draw.rect(screen, (30, 30, 30), pygame.Rect(0, 0, width, 90))
        screen.blit(font.render(f"Secuencia {current_sequence + 1}/{len(sequences)}", True, (255, 255, 255)), (20, 30))

        title = font.render(f"Actividad: {sequences[current_sequence]['title']}", True, (30, 30, 30))
        screen.blit(title, (430, 140))

        order_text = font.render(f"Pasos elegidos: {len(selected_order)}/{len(sequences[current_sequence]['correct_order'])}", True, (30, 30, 30))
        screen.blit(order_text, (420, 190))

        for button in step_buttons:
            color = (80, 170, 255) if not button["used"] else (160, 160, 160)
            pygame.draw.rect(screen, color, button["rect"], border_radius=12)
            pygame.draw.rect(screen, (20, 20, 20), button["rect"], 2, border_radius=12)
            txt = font.render(button["label"], True, (255, 255, 255))
            txt_rect = txt.get_rect(center=button["rect"].center)
            screen.blit(txt, txt_rect)

    def draw_result():
        screen.fill((18, 24, 32))
        screen.blit(title_font.render("Resultado guardado", True, (220, 255, 220)), (60, 100))
        screen.blit(font.render(f"Métrica principal: {final_metric} {final_unit}", True, (240, 240, 240)), (60, 200))
        screen.blit(font.render("ENTER o ESC para volver.", True, (255, 220, 120)), (60, 280))

    running = True

    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif state == "intro" and event.key == pygame.K_SPACE:
                    state = "playing"
                    current_sequence = 0
                    correct_count = 0
                    build_buttons()
                elif state == "result" and event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                    running = False

            elif event.type == pygame.MOUSEBUTTONDOWN and state == "playing":
                for button in step_buttons:
                    if button["rect"].collidepoint(event.pos) and not button["used"]:
                        button["used"] = True
                        selected_order.append(button["label"])

                        if len(selected_order) == len(sequences[current_sequence]["correct_order"]):
                            if selected_order == sequences[current_sequence]["correct_order"]:
                                correct_count += 1

                            current_sequence += 1

                            if current_sequence >= len(sequences):
                                final_metric = correct_count
                                save_result_json(patient_id, test_key, final_metric, final_unit, attempts)
                                state = "result"
                            else:
                                build_buttons()
                        break

        if state == "intro":
            draw_intro()
        elif state == "playing":
            draw_playing()
        else:
            draw_result()

        pygame.display.flip()
        clock.tick(60)

    pygame.quit()



# ============================================================
# INTERFAZ TKINTER PRINCIPAL
# ============================================================

#Maneja la interfaz del sistema. Antes y después de los juegos.
class OpenRehabApp:
  

    def __init__(self, root):
        self.root = root
        self.root.title(APP_TITLE)
        self.root.geometry("1100x720")
        self.root.minsize(980, 640)
        self.root.configure(bg="#10151c")

        # Variables de estado de la app.
        self.patient_id_var = tk.StringVar()
        self.selected_test_var = tk.StringVar(value=list(AREA_1_TESTS.keys())[0])
        self.current_area_key = tk.StringVar(value="area1")

        # Frame general que vamos a reconstruir cuando cambie de pantalla.
        self.main_container = tk.Frame(self.root, bg="#10151c")
        self.main_container.pack(fill="both", expand=True)

        # Arrancamos en la pantalla inicial / login.
        self.build_login_screen()

    # --------------------------------------------------------
    # UTILIDAD: limpiar pantalla antes de renderizar otra
    # --------------------------------------------------------
    def clear_main(self):
        for widget in self.main_container.winfo_children():
            widget.destroy()

    # --------------------------------------------------------
    # PANTALLA 1: LOGIN / CARGAR PARTIDA
    # --------------------------------------------------------
    def build_login_screen(self):
        self.clear_main()

        self.root.bind("<Return>", lambda event: self.handle_load_patient())

        bg_main = "#0A2540"
        bg_card = "#163A63"
        border_card = "#2B5C88"
        text_primary = "#F4F8FC"
        text_secondary = "#C7D9EA"
        btn_primary = "#72D39A"
        btn_primary_active = "#5FC187"
        btn_secondary = "#243B53"
        btn_secondary_active = "#1D3146"
        accent_1 = "#214A70"
        accent_2 = "#35688F"
        accent_3 = "#2D5E86"
        accent_blue = "#4FC3F7"
        accent_green = "#8BE3AE"

        outer = tk.Frame(self.main_container, bg=bg_main)
        outer.pack(fill="both", expand=True)

        top_band = tk.Frame(outer, bg="#102F4E", height=16)
        top_band.pack(fill="x", side="top")

        header = tk.Frame(outer, bg=bg_main)
        header.pack(fill="x", pady=(38, 12))

        tk.Label(
            header,
            text="OpenRehab ACV",
            font=("Arial", 32, "bold"),
            fg=text_primary,
            bg=bg_main
        ).pack()

        tk.Label(
            header,
            text="Ingeniería en Rehabilitación · Ciclo 2026",
            font=("Arial", 14),
            fg=text_secondary,
            bg=bg_main
        ).pack(pady=(6, 0))

        center = tk.Frame(outer, bg=bg_main)
        center.pack(expand=True)

        # Decoración izquierda
        left_deco = tk.Frame(center, bg=bg_main, width=170, height=320)
        left_deco.grid(row=0, column=0, padx=(35, 10))
        left_deco.grid_propagate(False)

        tk.Label(
            left_deco,
            text="◌",
            font=("Arial", 42),
            fg=accent_3,
            bg=bg_main
        ).place(relx=0.35, rely=0.28, anchor="center")

        tk.Label(
            left_deco,
            text="◍",
            font=("Arial", 54),
            fg=accent_1,
            bg=bg_main
        ).place(relx=0.58, rely=0.52, anchor="center")

        tk.Label(
            left_deco,
            text="◌",
            font=("Arial", 26),
            fg=accent_2,
            bg=bg_main
        ).place(relx=0.47, rely=0.74, anchor="center")

        # Tarjeta central
        card = tk.Frame(
            center,
            bg=bg_card,
            width=470,
            height=315,
            highlightthickness=1,
            highlightbackground=border_card
        )
        card.grid(row=0, column=1, padx=18, pady=10)
        card.grid_propagate(False)

        glow = tk.Frame(card, bg="#1D4D7F", height=8)
        glow.pack(fill="x", side="top")

        tk.Frame(card, bg=bg_card, height=30).pack()

        tk.Label(
            card,
            text="ID del paciente",
            font=("Arial", 12),
            fg=text_secondary,
            bg=bg_card
        ).pack(anchor="w", padx=42, pady=(0, 8))

        self.patient_entry = tk.Entry(
            card,
            font=("Arial", 16),
            bg="white",
            fg="#111111",
            insertbackground="#111111",
            relief="flat",
            bd=0
        )
        self.patient_entry.pack(fill="x", padx=42, ipady=12)
        self.patient_entry.focus_set()

        tk.Label(
            card,
            text="Podés cargar una partida previa usando el mismo ID.",
            font=("Arial", 10),
            fg="#8FB1CC",
            bg=bg_card
        ).pack(anchor="w", padx=42, pady=(12, 20))

        history_row = tk.Frame(card, bg=bg_card)
        history_row.pack(fill="x", padx=42, pady=(0, 18))

        tk.Label(
            history_row,
            text="☑",
            font=("Arial", 12),
            fg=accent_green,
            bg=bg_card
        ).pack(side="left")

        tk.Label(
            history_row,
            text="Mostrar historial de pruebas previas",
            font=("Arial", 11),
            fg=text_secondary,
            bg=bg_card
        ).pack(side="left", padx=(8, 0))

        tk.Button(
            card,
            text="Acceder",
            font=("Arial", 16, "bold"),
            bg=btn_primary,
            fg="white",
            activebackground=btn_primary_active,
            activeforeground="white",
            relief="flat",
            bd=0,
            cursor="hand2",
            command=self.handle_load_patient
        ).pack(fill="x", padx=34, ipady=12)

        tk.Frame(card, bg=bg_card, height=12).pack()

        tk.Button(
            card,
            text="Salir",
            font=("Arial", 15, "bold"),
            bg=btn_secondary,
            fg="white",
            activebackground=btn_secondary_active,
            activeforeground="white",
            relief="flat",
            bd=0,
            cursor="hand2",
            command=self.root.destroy
        ).pack(fill="x", padx=34, ipady=10)

        footer = tk.Label(
            card,
            text="Plataforma de evaluación y rehabilitación neurológica",
            font=("Arial", 10),
            fg="#8FB1CC",
            bg=bg_card
        )
        footer.pack(pady=(16, 0))

        # Decoración derecha
        right_deco = tk.Frame(center, bg=bg_main, width=170, height=320)
        right_deco.grid(row=0, column=2, padx=(10, 35))
        right_deco.grid_propagate(False)

        tk.Label(
            right_deco,
            text="◌",
            font=("Arial", 50),
            fg=accent_1,
            bg=bg_main
        ).place(relx=0.42, rely=0.30, anchor="center")

        tk.Label(
            right_deco,
            text="◍",
            font=("Arial", 32),
            fg=accent_2,
            bg=bg_main
        ).place(relx=0.62, rely=0.54, anchor="center")

        tk.Label(
            right_deco,
            text="◌",
            font=("Arial", 24),
            fg=accent_3,
            bg=bg_main
        ).place(relx=0.50, rely=0.76, anchor="center")

        bottom_wrap = tk.Frame(outer, bg=bg_main)
        bottom_wrap.pack(fill="x", side="bottom")

        wave_2 = tk.Frame(bottom_wrap, bg=accent_green, height=4)
        wave_2.pack(fill="x", side="bottom")

        wave_1 = tk.Frame(bottom_wrap, bg=accent_blue, height=10)
        wave_1.pack(fill="x", side="bottom")
    # --------------------------------------------------------
    # VALIDACIÓN / CARGA DEL PACIENTE
    # --------------------------------------------------------
    def handle_load_patient(self):
        patient_id = self.patient_entry.get().strip()

        if not patient_id:
            messagebox.showwarning(
                "Falta información",
                "Ingresá un ID de paciente para continuar."
            )
            return

        self.patient_id_var.set(patient_id)
        self.build_area_selector(patient_id)

    # --------------------------------------------------------
    # SELECCIÓN DE ÁREA DE TRABAJO
    #---------------------------------------------------------
    def build_area_selector(self, patient_id: str):
        self.clear_main()
        self.root.unbind("<Return>")

        bg_main = "#0A2540"
        bg_card = "#163A63"
        border_card = "#2B5C88"
        text_primary = "#F4F8FC"
        text_secondary = "#C7D9EA"
        btn_primary = "#72D39A"
        btn_primary_active = "#5FC187"
        btn_secondary = "#243B53"
        btn_secondary_active = "#1D3146"
        accent_blue = "#4FC3F7"
        accent_green = "#8BE3AE"

        descriptions = {
            "area1": "Visión y Percepción: ejercicios orientados a atención visual, exploración espacial, discriminación figura-fondo y seguimiento de estímulos.",
            "area2": "Control Motor y Acceso: actividades enfocadas en precisión, trayectorias, coordinación, fuerza controlada y fatiga del miembro superior.",
            "area3": "Cognición y Lenguaje: tareas de memoria, lenguaje, planificación, inhibición y razonamiento para funciones ejecutivas."
        }

        outer = tk.Frame(self.main_container, bg=bg_main)
        outer.pack(fill="both", expand=True)

        top_band = tk.Frame(outer, bg="#102F4E", height=16)
        top_band.pack(fill="x", side="top")

        header = tk.Frame(outer, bg=bg_main)
        header.pack(fill="x", pady=(30, 10))

        tk.Label(
            header,
            text="OpenRehab ACV",
            font=("Arial", 30, "bold"),
            fg=text_primary,
            bg=bg_main
        ).pack()

        tk.Label(
            header,
            text=f"Paciente cargado: {patient_id}",
            font=("Arial", 13),
            fg=text_secondary,
            bg=bg_main
        ).pack(pady=(8, 0))

        tk.Label(
            header,
            text="Seleccioná un área para comenzar",
            font=("Arial", 16),
            fg=text_primary,
            bg=bg_main
        ).pack(pady=(14, 0))

        content = tk.Frame(outer, bg=bg_main)
        content.pack(expand=True)

        card = tk.Frame(
            content,
            bg=bg_card,
            width=820,
            height=420,
            highlightthickness=1,
            highlightbackground=border_card
        )
        card.pack(pady=10)
        card.pack_propagate(False)

        glow = tk.Frame(card, bg="#1D4D7F", height=8)
        glow.pack(fill="x", side="top")

        tk.Frame(card, bg=bg_card, height=28).pack()

        tk.Label(
            card,
            text="Elegí una de las áreas de trabajo",
            font=("Arial", 18, "bold"),
            fg=text_primary,
            bg=bg_card
        ).pack()

        tk.Label(
            card,
            text="Pasá el mouse sobre cada opción para ver una breve descripción",
            font=("Arial", 11),
            fg=text_secondary,
            bg=bg_card
        ).pack(pady=(6, 18))

        buttons_row = tk.Frame(card, bg=bg_card)
        buttons_row.pack(pady=(6, 18))

        description_frame = tk.Frame(
            card,
            bg="#102F4E",
            width=700,
            height=110,
            highlightthickness=1,
            highlightbackground="#2B5C88"
        )
        description_frame.pack()
        description_frame.pack_propagate(False)

        description_title = tk.Label(
            description_frame,
            text="Descripción del área",
            font=("Arial", 13, "bold"),
            fg=text_primary,
            bg="#102F4E"
        )
        description_title.pack(anchor="w", padx=18, pady=(14, 6))

        description_label = tk.Label(
            description_frame,
            text="Posicioná el cursor sobre un botón para ver su descripción.",
            font=("Arial", 11),
            fg=text_secondary,
            bg="#102F4E",
            justify="left",
            wraplength=660
        )
        description_label.pack(anchor="w", padx=18)

        def show_description(area_key):
            if area_key == "area1":
                description_title.config(text="Área 1 · Visión y Percepción")
            elif area_key == "area2":
                description_title.config(text="Área 2 · Control Motor y Acceso")
            elif area_key == "area3":
                description_title.config(text="Área 3 · Cognición y Lenguaje")

            description_label.config(text=descriptions[area_key])

        def reset_description(event=None):
            description_title.config(text="Descripción del área")
            description_label.config(text="Posicioná el cursor sobre un botón para ver su descripción.")

        def open_area(area_key):
            if area_key == "area1":
                self.current_area_key.set("area1")
                self.selected_test_var.set(list(AREA_1_TESTS.keys())[0])
                self.build_area1_menu(patient_id)

            elif area_key == "area2":
                self.current_area_key.set("area2")
                self.selected_test_var.set(list(AREA_2_TESTS.keys())[0])
                self.build_area2_menu(patient_id)

            elif area_key == "area3":
                self.current_area_key.set("area3")
                self.selected_test_var.set(list(AREA_3_TESTS.keys())[0])
                self.build_area3_menu(patient_id)

        area1_btn = tk.Button(
            buttons_row,
            text="Área 1\nVisión y Percepción",
            font=("Arial", 13, "bold"),
            bg=btn_primary,
            fg="white",
            activebackground=btn_primary_active,
            activeforeground="white",
            relief="flat",
            bd=0,
            cursor="hand2",
            width=19,
            height=4,
            command=lambda: open_area("area1")
        )
        area1_btn.grid(row=0, column=0, padx=10)

        area2_btn = tk.Button(
            buttons_row,
            text="Área 2\nControl Motor y Acceso",
            font=("Arial", 13, "bold"),
            bg=btn_secondary,
            fg="white",
            activebackground=btn_secondary_active,
            activeforeground="white",
            relief="flat",
            bd=0,
            cursor="hand2",
            width=19,
            height=4,
            command=lambda: open_area("area2")
        )
        area2_btn.grid(row=0, column=1, padx=10)

        area3_btn = tk.Button(
            buttons_row,
            text="Área 3\nCognición y Lenguaje",
            font=("Arial", 13, "bold"),
            bg="#30506F",
            fg="white",
            activebackground="#27445F",
            activeforeground="white",
            relief="flat",
            bd=0,
            cursor="hand2",
            width=19,
            height=4,
            command=lambda: open_area("area3")
        )
        area3_btn.grid(row=0, column=2, padx=10)

        area1_btn.bind("<Enter>", lambda event: show_description("area1"))
        area2_btn.bind("<Enter>", lambda event: show_description("area2"))
        area3_btn.bind("<Enter>", lambda event: show_description("area3"))

        area1_btn.bind("<Leave>", reset_description)
        area2_btn.bind("<Leave>", reset_description)
        area3_btn.bind("<Leave>", reset_description)

        bottom_buttons = tk.Frame(card, bg=bg_card)
        bottom_buttons.pack(fill="x", padx=34, pady=(22, 0))

        back_button = tk.Button(
            bottom_buttons,
            text="Volver",
            font=("Arial", 13, "bold"),
            bg=btn_secondary,
            fg="white",
            activebackground=btn_secondary_active,
            activeforeground="white",
            relief="flat",
            bd=0,
            cursor="hand2",
            command=self.build_login_screen
        )
        back_button.pack(side="left", ipadx=24, ipady=8)

        continue_hint = tk.Label(
            bottom_buttons,
            text="Seleccioná un área para continuar",
            font=("Arial", 11),
            fg=text_secondary,
            bg=bg_card
        )
        continue_hint.pack(side="right")

        bottom_wrap = tk.Frame(outer, bg=bg_main)
        bottom_wrap.pack(fill="x", side="bottom")

        wave_2 = tk.Frame(bottom_wrap, bg=accent_green, height=4)
        wave_2.pack(fill="x", side="bottom")

        wave_1 = tk.Frame(bottom_wrap, bg=accent_blue, height=10)
        wave_1.pack(fill="x", side="bottom")


    # --------------------------------------------------------
    # PANTALLA 3: MENÚ DEL ÁREA 1 + HISTORIAL
    # --------------------------------------------------------
    def build_area1_menu(self, patient_id: str):
        self.clear_main()
        self.root.unbind("<Return>")

        bg_main = "#0A2540"
        bg_card = "#163A63"
        border_card = "#2B5C88"
        text_primary = "#F4F8FC"
        text_secondary = "#C7D9EA"
        btn_primary = "#72D39A"
        btn_primary_active = "#5FC187"
        btn_secondary = "#243B53"
        btn_secondary_active = "#1D3146"
        accent_blue = "#4FC3F7"
        accent_green = "#8BE3AE"

        outer = tk.Frame(self.main_container, bg=bg_main)
        outer.pack(fill="both", expand=True)

        top_band = tk.Frame(outer, bg="#102F4E", height=16)
        top_band.pack(fill="x", side="top")

        header = tk.Frame(outer, bg=bg_main)
        header.pack(fill="x", pady=(26, 10), padx=24)

        tk.Label(
            header,
            text="OpenRehab ACV",
            font=("Arial", 28, "bold"),
            fg=text_primary,
            bg=bg_main
        ).pack(anchor="w")

        tk.Label(
            header,
            text=f"Área 1 · Visión y Percepción   |   Paciente: {patient_id}",
            font=("Arial", 13),
            fg=text_secondary,
            bg=bg_main
        ).pack(anchor="w", pady=(6, 0))

        content = tk.Frame(outer, bg=bg_main)
        content.pack(fill="both", expand=True, padx=24, pady=(8, 18))

        left_panel = tk.Frame(
            content,
            bg=bg_card,
            highlightthickness=1,
            highlightbackground=border_card
        )
        left_panel.pack(side="left", fill="both", expand=True, padx=(0, 10))

        right_panel = tk.Frame(
            content,
            bg=bg_card,
            highlightthickness=1,
            highlightbackground=border_card
        )
        right_panel.pack(side="right", fill="both", expand=True, padx=(10, 0))

        # -----------------------------
        # PANEL IZQUIERDO
        # -----------------------------
        tk.Frame(left_panel, bg="#1D4D7F", height=8).pack(fill="x", side="top")

        tk.Label(
            left_panel,
            text="Seleccionar test",
            font=("Arial", 18, "bold"),
            fg=text_primary,
            bg=bg_card
        ).pack(anchor="w", padx=20, pady=(20, 8))

        tk.Label(
            left_panel,
            text="Elegí una actividad del Área 1 para comenzar.",
            font=("Arial", 11),
            fg=text_secondary,
            bg=bg_card
        ).pack(anchor="w", padx=20, pady=(0, 14))

        combo_style = ttk.Style()
        combo_style.theme_use("default")
        combo_style.configure(
            "OpenRehab.TCombobox",
            fieldbackground="white",
            background="white",
            foreground="#111111",
            padding=8
        )

        combo = ttk.Combobox(
            left_panel,
            textvariable=self.selected_test_var,
            values=list(AREA_1_TESTS.keys()),
            state="readonly",
            font=("Arial", 12),
            style="OpenRehab.TCombobox"
        )
        combo.pack(fill="x", padx=20, pady=(0, 10))

        pretty_name_label = tk.Label(
            left_panel,
            text=AREA_1_TESTS[self.selected_test_var.get()],
            font=("Arial", 13),
            fg=text_primary,
            bg=bg_card,
            wraplength=430,
            justify="left"
        )
        pretty_name_label.pack(anchor="w", padx=20, pady=(0, 14))

        compare_box = tk.Frame(
            left_panel,
            bg="#102F4E",
            highlightthickness=1,
            highlightbackground=border_card
        )
        compare_box.pack(fill="x", padx=20, pady=(0, 16))

        compare_title = tk.Label(
            compare_box,
            text="Comparación con intentos previos",
            font=("Arial", 12, "bold"),
            fg=text_primary,
            bg="#102F4E"
        )
        compare_title.pack(anchor="w", padx=14, pady=(14, 8))

        comparison_text = tk.Label(
            compare_box,
            text="Seleccioná un test para ver historial comparativo.",
            font=("Arial", 11),
            fg=text_secondary,
            bg="#102F4E",
            justify="left",
            wraplength=430
        )
        comparison_text.pack(anchor="w", padx=14, pady=(0, 14))

        def refresh_comparison(*args):
            test_key = self.selected_test_var.get()
            pretty_name_label.config(text=AREA_1_TESTS[test_key])

            last_result = get_last_result_for_test(patient_id, test_key)

            if last_result:
                metric = last_result.get("metrica_principal", "-")
                unit = last_result.get("unidad", "-")
                date = last_result.get("fecha", "-")
                attempts = last_result.get("intentos", "-")

                comparison_text.config(
                    text=(
                        f"Último resultado encontrado:\n\n"
                        f"• Fecha: {date}\n"
                        f"• Métrica principal: {metric} {unit}\n"
                        f"• Intentos: {attempts}\n\n"
                        f"Al finalizar un nuevo intento se guardará otro JSON en /results."
                    )
                )
            else:
                comparison_text.config(
                    text=(
                        "No hay resultados previos para este test y este paciente.\n\n"
                        "Al finalizar el primer intento, el sistema guardará un JSON en /results."
                    )
                )

        combo.bind("<<ComboboxSelected>>", refresh_comparison)
        refresh_comparison()

        buttons_row = tk.Frame(left_panel, bg=bg_card)
        buttons_row.pack(fill="x", padx=20, pady=(4, 20))

        launch_button = tk.Button(
            buttons_row,
            text="Comenzar test",
            font=("Arial", 13, "bold"),
            bg=btn_primary,
            fg="white",
            activebackground=btn_primary_active,
            activeforeground="white",
            relief="flat",
            bd=0,
            cursor="hand2",
            command=lambda: self.launch_selected_test(patient_id)
        )
        launch_button.pack(side="left", fill="x", expand=True, ipady=10)

        back_button = tk.Button(
            buttons_row,
            text="Volver al menú de áreas",
            font=("Arial", 12, "bold"),
            bg=btn_secondary,
            fg="white",
            activebackground=btn_secondary_active,
            activeforeground="white",
            relief="flat",
            bd=0,
            cursor="hand2",
            command=lambda: self.build_area_selector(patient_id)
        )
        back_button.pack(side="left", fill="x", expand=True, padx=(12, 0), ipady=10)

        # -----------------------------
        # PANEL DERECHO
        # -----------------------------
        tk.Frame(right_panel, bg="#1D4D7F", height=8).pack(fill="x", side="top")

        tk.Label(
            right_panel,
            text="Historial del paciente",
            font=("Arial", 18, "bold"),
            fg=text_primary,
            bg=bg_card
        ).pack(anchor="w", padx=20, pady=(20, 8))

        tk.Label(
            right_panel,
            text="Resultados guardados en la carpeta /results.",
            font=("Arial", 11),
            fg=text_secondary,
            bg=bg_card
        ).pack(anchor="w", padx=20, pady=(0, 14))

        history_results = load_patient_results(patient_id)

        history_container = tk.Frame(
            right_panel,
            bg="#102F4E",
            highlightthickness=1,
            highlightbackground=border_card
        )
        history_container.pack(fill="both", expand=True, padx=20, pady=(0, 20))

        history_scroll = tk.Scrollbar(history_container)
        history_scroll.pack(side="right", fill="y")

        history_list = tk.Text(
            history_container,
            yscrollcommand=history_scroll.set,
            bg="#102F4E",
            fg=text_primary,
            font=("Consolas", 10),
            wrap="word",
            relief="flat",
            padx=14,
            pady=14,
            insertbackground=text_primary
        )
        history_list.pack(side="left", fill="both", expand=True)

        history_scroll.config(command=history_list.yview)

        if history_results:
            for item in history_results:
                test_name = AREA_1_TESTS.get(item.get("test", ""), item.get("test", "Test desconocido"))
                line = (
                    f"Fecha: {item.get('fecha', '-')}\n"
                    f"Test: {test_name}\n"
                    f"Métrica: {item.get('metrica_principal', '-')} {item.get('unidad', '-')}\n"
                    f"Intentos: {item.get('intentos', '-')}\n"
                    f"Archivo: {item.get('__file', '-')}\n"
                    f"{'-' * 58}\n"
                )
                history_list.insert("end", line)
        else:
            history_list.insert(
                "end",
                "No se encontraron resultados previos para este paciente en la carpeta /results.\n"
            )

        history_list.config(state="disabled")

        bottom_wrap = tk.Frame(outer, bg=bg_main)
        bottom_wrap.pack(fill="x", side="bottom")

        wave_2 = tk.Frame(bottom_wrap, bg=accent_green, height=4)
        wave_2.pack(fill="x", side="bottom")

        wave_1 = tk.Frame(bottom_wrap, bg=accent_blue, height=10)
        wave_1.pack(fill="x", side="bottom")
  
    # --------------------------------------------------------
    # PANTALLA 4: MENÚ DEL ÁREA 2 + HISTORIAL
    # --------------------------------------------------------
    def build_area2_menu(self, patient_id: str):
        self.clear_main()
        self.root.unbind("<Return>")

        bg_main = "#0A2540"
        bg_card = "#163A63"
        border_card = "#2B5C88"
        text_primary = "#F4F8FC"
        text_secondary = "#C7D9EA"
        btn_primary = "#72D39A"
        btn_primary_active = "#5FC187"
        btn_secondary = "#243B53"
        btn_secondary_active = "#1D3146"
        accent_blue = "#4FC3F7"
        accent_green = "#8BE3AE"

        outer = tk.Frame(self.main_container, bg=bg_main)
        outer.pack(fill="both", expand=True)

        top_band = tk.Frame(outer, bg="#102F4E", height=16)
        top_band.pack(fill="x", side="top")

        header = tk.Frame(outer, bg=bg_main)
        header.pack(fill="x", pady=(26, 10), padx=24)

        tk.Label(
            header,
            text="OpenRehab ACV",
            font=("Arial", 28, "bold"),
            fg=text_primary,
            bg=bg_main
        ).pack(anchor="w")

        tk.Label(
            header,
            text=f"Área 2 · Control Motor y Acceso   |   Paciente: {patient_id}",
            font=("Arial", 13),
            fg=text_secondary,
            bg=bg_main
        ).pack(anchor="w", pady=(6, 0))

        content = tk.Frame(outer, bg=bg_main)
        content.pack(fill="both", expand=True, padx=24, pady=(8, 18))

        left_panel = tk.Frame(
            content,
            bg=bg_card,
            highlightthickness=1,
            highlightbackground=border_card
        )
        left_panel.pack(side="left", fill="both", expand=True, padx=(0, 10))

        right_panel = tk.Frame(
            content,
            bg=bg_card,
            highlightthickness=1,
            highlightbackground=border_card
        )
        right_panel.pack(side="right", fill="both", expand=True, padx=(10, 0))

        tk.Frame(left_panel, bg="#1D4D7F", height=8).pack(fill="x", side="top")

        tk.Label(
            left_panel,
            text="Seleccionar test",
            font=("Arial", 18, "bold"),
            fg=text_primary,
            bg=bg_card
        ).pack(anchor="w", padx=20, pady=(20, 8))

        tk.Label(
            left_panel,
            text="Elegí una actividad del Área 2 para comenzar.",
            font=("Arial", 11),
            fg=text_secondary,
            bg=bg_card
        ).pack(anchor="w", padx=20, pady=(0, 14))

        combo_style = ttk.Style()
        combo_style.theme_use("default")
        combo_style.configure(
            "OpenRehab.TCombobox",
            fieldbackground="white",
            background="white",
            foreground="#111111",
            padding=8
        )

        combo = ttk.Combobox(
            left_panel,
            textvariable=self.selected_test_var,
            values=list(AREA_2_TESTS.keys()),
            state="readonly",
            font=("Arial", 12),
            style="OpenRehab.TCombobox"
        )
        combo.pack(fill="x", padx=20, pady=(0, 10))

        pretty_name_label = tk.Label(
            left_panel,
            text=AREA_2_TESTS[self.selected_test_var.get()],
            font=("Arial", 13),
            fg=text_primary,
            bg=bg_card,
            wraplength=430,
            justify="left"
        )
        pretty_name_label.pack(anchor="w", padx=20, pady=(0, 14))

        compare_box = tk.Frame(
            left_panel,
            bg="#102F4E",
            highlightthickness=1,
            highlightbackground=border_card
        )
        compare_box.pack(fill="x", padx=20, pady=(0, 16))

        tk.Label(
            compare_box,
            text="Comparación con intentos previos",
            font=("Arial", 12, "bold"),
            fg=text_primary,
            bg="#102F4E"
        ).pack(anchor="w", padx=14, pady=(14, 8))

        comparison_text = tk.Label(
            compare_box,
            text="Seleccioná un test para ver historial comparativo.",
            font=("Arial", 11),
            fg=text_secondary,
            bg="#102F4E",
            justify="left",
            wraplength=430
        )
        comparison_text.pack(anchor="w", padx=14, pady=(0, 14))

        def refresh_comparison(*args):
            test_key = self.selected_test_var.get()
            pretty_name_label.config(text=AREA_2_TESTS[test_key])

            last_result = get_last_result_for_test(patient_id, test_key)

            if last_result:
                metric = last_result.get("metrica_principal", "-")
                unit = last_result.get("unidad", "-")
                date = last_result.get("fecha", "-")
                attempts = last_result.get("intentos", "-")

                comparison_text.config(
                    text=(
                        f"Último resultado encontrado:\n\n"
                        f"• Fecha: {date}\n"
                        f"• Métrica principal: {metric} {unit}\n"
                        f"• Intentos: {attempts}\n\n"
                        f"Al finalizar un nuevo intento se guardará otro JSON en /results."
                    )
                )
            else:
                comparison_text.config(
                    text=(
                        "No hay resultados previos para este test y este paciente.\n\n"
                        "Al finalizar el primer intento, el sistema guardará un JSON en /results."
                    )
                )

        combo.bind("<<ComboboxSelected>>", refresh_comparison)
        refresh_comparison()

        buttons_row = tk.Frame(left_panel, bg=bg_card)
        buttons_row.pack(fill="x", padx=20, pady=(4, 20))

        launch_button = tk.Button(
            buttons_row,
            text="Comenzar test",
            font=("Arial", 13, "bold"),
            bg=btn_primary,
            fg="white",
            activebackground=btn_primary_active,
            activeforeground="white",
            relief="flat",
            bd=0,
            cursor="hand2",
            command=lambda: self.launch_selected_test(patient_id)
        )
        launch_button.pack(side="left", fill="x", expand=True, ipady=10)

        back_button = tk.Button(
            buttons_row,
            text="Volver al menú de áreas",
            font=("Arial", 12, "bold"),
            bg=btn_secondary,
            fg="white",
            activebackground=btn_secondary_active,
            activeforeground="white",
            relief="flat",
            bd=0,
            cursor="hand2",
            command=lambda: self.build_area_selector(patient_id)
        )
        back_button.pack(side="left", fill="x", expand=True, padx=(12, 0), ipady=10)

        tk.Frame(right_panel, bg="#1D4D7F", height=8).pack(fill="x", side="top")

        tk.Label(
            right_panel,
            text="Historial del paciente",
            font=("Arial", 18, "bold"),
            fg=text_primary,
            bg=bg_card
        ).pack(anchor="w", padx=20, pady=(20, 8))

        tk.Label(
            right_panel,
            text="Resultados guardados en la carpeta /results.",
            font=("Arial", 11),
            fg=text_secondary,
            bg=bg_card
        ).pack(anchor="w", padx=20, pady=(0, 14))

        history_results = load_patient_results(patient_id)

        history_container = tk.Frame(
            right_panel,
            bg="#102F4E",
            highlightthickness=1,
            highlightbackground=border_card
        )
        history_container.pack(fill="both", expand=True, padx=20, pady=(0, 20))

        history_scroll = tk.Scrollbar(history_container)
        history_scroll.pack(side="right", fill="y")

        history_list = tk.Text(
            history_container,
            yscrollcommand=history_scroll.set,
            bg="#102F4E",
            fg=text_primary,
            font=("Consolas", 10),
            wrap="word",
            relief="flat",
            padx=14,
            pady=14,
            insertbackground=text_primary
        )
        history_list.pack(side="left", fill="both", expand=True)

        history_scroll.config(command=history_list.yview)

        if history_results:
            for item in history_results:
                test_name = AREA_2_TESTS.get(item.get("test", ""), item.get("test", "Test desconocido"))
                line = (
                    f"Fecha: {item.get('fecha', '-')}\n"
                    f"Test: {test_name}\n"
                    f"Métrica: {item.get('metrica_principal', '-')} {item.get('unidad', '-')}\n"
                    f"Intentos: {item.get('intentos', '-')}\n"
                    f"Archivo: {item.get('__file', '-')}\n"
                    f"{'-' * 58}\n"
                )
                history_list.insert("end", line)
        else:
            history_list.insert(
                "end",
                "No se encontraron resultados previos para este paciente en la carpeta /results.\n"
            )

        history_list.config(state="disabled")

        bottom_wrap = tk.Frame(outer, bg=bg_main)
        bottom_wrap.pack(fill="x", side="bottom")

        wave_2 = tk.Frame(bottom_wrap, bg=accent_green, height=4)
        wave_2.pack(fill="x", side="bottom")

        wave_1 = tk.Frame(bottom_wrap, bg=accent_blue, height=10)
        wave_1.pack(fill="x", side="bottom")

    # --------------------------------------------------------
    # PANTALLA 5: MENÚ DEL ÁREA 3 + HISTORIAL
    # --------------------------------------------------------

    def build_area3_menu(self, patient_id: str):
        self.clear_main()
        self.root.unbind("<Return>")

        bg_main = "#0A2540"
        bg_card = "#163A63"
        border_card = "#2B5C88"
        text_primary = "#F4F8FC"
        text_secondary = "#C7D9EA"
        btn_primary = "#72D39A"
        btn_primary_active = "#5FC187"
        btn_secondary = "#243B53"
        btn_secondary_active = "#1D3146"
        accent_blue = "#4FC3F7"
        accent_green = "#8BE3AE"

        outer = tk.Frame(self.main_container, bg=bg_main)
        outer.pack(fill="both", expand=True)

        top_band = tk.Frame(outer, bg="#102F4E", height=16)
        top_band.pack(fill="x", side="top")

        header = tk.Frame(outer, bg=bg_main)
        header.pack(fill="x", pady=(26, 10), padx=24)

        tk.Label(
            header,
            text="OpenRehab ACV",
            font=("Arial", 28, "bold"),
            fg=text_primary,
            bg=bg_main
        ).pack(anchor="w")

        tk.Label(
            header,
            text=f"Área 3 · Cognición y Lenguaje   |   Paciente: {patient_id}",
            font=("Arial", 13),
            fg=text_secondary,
            bg=bg_main
        ).pack(anchor="w", pady=(6, 0))

        content = tk.Frame(outer, bg=bg_main)
        content.pack(fill="both", expand=True, padx=24, pady=(8, 18))

        left_panel = tk.Frame(
            content,
            bg=bg_card,
            highlightthickness=1,
            highlightbackground=border_card
        )
        left_panel.pack(side="left", fill="both", expand=True, padx=(0, 10))

        right_panel = tk.Frame(
            content,
            bg=bg_card,
            highlightthickness=1,
            highlightbackground=border_card
        )
        right_panel.pack(side="right", fill="both", expand=True, padx=(10, 0))

        tk.Frame(left_panel, bg="#1D4D7F", height=8).pack(fill="x", side="top")

        tk.Label(
            left_panel,
            text="Seleccionar test",
            font=("Arial", 18, "bold"),
            fg=text_primary,
            bg=bg_card
        ).pack(anchor="w", padx=20, pady=(20, 8))

        tk.Label(
            left_panel,
            text="Elegí una actividad del Área 3 para comenzar.",
            font=("Arial", 11),
            fg=text_secondary,
            bg=bg_card
        ).pack(anchor="w", padx=20, pady=(0, 14))

        combo_style = ttk.Style()
        combo_style.theme_use("default")
        combo_style.configure(
            "OpenRehab.TCombobox",
            fieldbackground="white",
            background="white",
            foreground="#111111",
            padding=8
        )

        combo = ttk.Combobox(
            left_panel,
            textvariable=self.selected_test_var,
            values=list(AREA_3_TESTS.keys()),
            state="readonly",
            font=("Arial", 12),
            style="OpenRehab.TCombobox"
        )
        combo.pack(fill="x", padx=20, pady=(0, 10))

        pretty_name_label = tk.Label(
            left_panel,
            text=AREA_3_TESTS[self.selected_test_var.get()],
            font=("Arial", 13),
            fg=text_primary,
            bg=bg_card,
            wraplength=430,
            justify="left"
        )
        pretty_name_label.pack(anchor="w", padx=20, pady=(0, 14))

        compare_box = tk.Frame(
            left_panel,
            bg="#102F4E",
            highlightthickness=1,
            highlightbackground=border_card
        )
        compare_box.pack(fill="x", padx=20, pady=(0, 16))

        tk.Label(
            compare_box,
            text="Comparación con intentos previos",
            font=("Arial", 12, "bold"),
            fg=text_primary,
            bg="#102F4E"
        ).pack(anchor="w", padx=14, pady=(14, 8))

        comparison_text = tk.Label(
            compare_box,
            text="Seleccioná un test para ver historial comparativo.",
            font=("Arial", 11),
            fg=text_secondary,
            bg="#102F4E",
            justify="left",
            wraplength=430
        )
        comparison_text.pack(anchor="w", padx=14, pady=(0, 14))

        def refresh_comparison(*args):
            test_key = self.selected_test_var.get()
            pretty_name_label.config(text=AREA_3_TESTS[test_key])

            last_result = get_last_result_for_test(patient_id, test_key)

            if last_result:
                metric = last_result.get("metrica_principal", "-")
                unit = last_result.get("unidad", "-")
                date = last_result.get("fecha", "-")
                attempts = last_result.get("intentos", "-")

                comparison_text.config(
                    text=(
                        f"Último resultado encontrado:\n\n"
                        f"• Fecha: {date}\n"
                        f"• Métrica principal: {metric} {unit}\n"
                        f"• Intentos: {attempts}\n\n"
                        f"Al finalizar un nuevo intento se guardará otro JSON en /results."
                    )
                )
            else:
                comparison_text.config(
                    text=(
                        "No hay resultados previos para este test y este paciente.\n\n"
                        "Al finalizar el primer intento, el sistema guardará un JSON en /results."
                    )
                )

        combo.bind("<<ComboboxSelected>>", refresh_comparison)
        refresh_comparison()

        buttons_row = tk.Frame(left_panel, bg=bg_card)
        buttons_row.pack(fill="x", padx=20, pady=(4, 20))

        launch_button = tk.Button(
            buttons_row,
            text="Comenzar test",
            font=("Arial", 13, "bold"),
            bg=btn_primary,
            fg="white",
            activebackground=btn_primary_active,
            activeforeground="white",
            relief="flat",
            bd=0,
            cursor="hand2",
            command=lambda: self.launch_selected_test(patient_id)
        )
        launch_button.pack(side="left", fill="x", expand=True, ipady=10)

        back_button = tk.Button(
            buttons_row,
            text="Volver al menú de áreas",
            font=("Arial", 12, "bold"),
            bg=btn_secondary,
            fg="white",
            activebackground=btn_secondary_active,
            activeforeground="white",
            relief="flat",
            bd=0,
            cursor="hand2",
            command=lambda: self.build_area_selector(patient_id)
        )
        back_button.pack(side="left", fill="x", expand=True, padx=(12, 0), ipady=10)

        tk.Frame(right_panel, bg="#1D4D7F", height=8).pack(fill="x", side="top")

        tk.Label(
            right_panel,
            text="Historial del paciente",
            font=("Arial", 18, "bold"),
            fg=text_primary,
            bg=bg_card
        ).pack(anchor="w", padx=20, pady=(20, 8))

        tk.Label(
            right_panel,
            text="Resultados guardados en la carpeta /results.",
            font=("Arial", 11),
            fg=text_secondary,
            bg=bg_card
        ).pack(anchor="w", padx=20, pady=(0, 14))

        history_results = load_patient_results(patient_id)

        history_container = tk.Frame(
            right_panel,
            bg="#102F4E",
            highlightthickness=1,
            highlightbackground=border_card
        )
        history_container.pack(fill="both", expand=True, padx=20, pady=(0, 20))

        history_scroll = tk.Scrollbar(history_container)
        history_scroll.pack(side="right", fill="y")

        history_list = tk.Text(
            history_container,
            yscrollcommand=history_scroll.set,
            bg="#102F4E",
            fg=text_primary,
            font=("Consolas", 10),
            wrap="word",
            relief="flat",
            padx=14,
            pady=14,
            insertbackground=text_primary
        )
        history_list.pack(side="left", fill="both", expand=True)

        history_scroll.config(command=history_list.yview)

        if history_results:
            for item in history_results:
                test_name = AREA_3_TESTS.get(item.get("test", ""), item.get("test", "Test desconocido"))
                line = (
                    f"Fecha: {item.get('fecha', '-')}\n"
                    f"Test: {test_name}\n"
                    f"Métrica: {item.get('metrica_principal', '-')} {item.get('unidad', '-')}\n"
                    f"Intentos: {item.get('intentos', '-')}\n"
                    f"Archivo: {item.get('__file', '-')}\n"
                    f"{'-' * 58}\n"
                )
                history_list.insert("end", line)
        else:
            history_list.insert(
                "end",
                "No se encontraron resultados previos para este paciente en la carpeta /results.\n"
            )

        history_list.config(state="disabled")

        bottom_wrap = tk.Frame(outer, bg=bg_main)
        bottom_wrap.pack(fill="x", side="bottom")

        wave_2 = tk.Frame(bottom_wrap, bg=accent_green, height=4)
        wave_2.pack(fill="x", side="bottom")

        wave_1 = tk.Frame(bottom_wrap, bg=accent_blue, height=10)
        wave_1.pack(fill="x", side="bottom")


    # --------------------------------------------------------
    # LANZAR EL TEST ELEGIDO EN PYGAME
    # --------------------------------------------------------
    def launch_selected_test(self, patient_id: str):
        test_key = self.selected_test_var.get()

        if self.current_area_key.get() == "area1":
            tests_dict = AREA_1_TESTS
        elif self.current_area_key.get() == "area2":
            tests_dict = AREA_2_TESTS
        else:
            tests_dict = AREA_3_TESTS

        test_name = tests_dict[test_key]

        self.root.withdraw()
        try:
            if test_key == "exploracion_faro":
                    run_exploracion_faro_test(patient_id, test_key, test_name)

            elif test_key == "anclaje_visual":
                run_anclaje_visual_test(patient_id, test_key, test_name)

            elif test_key == "complejidad_gradual":
                run_complejidad_gradual_test(patient_id, test_key, test_name)

            elif test_key == "cancelacion_estimulos":
                run_cancelacion_estimulos_test(patient_id, test_key, test_name)

            elif test_key == "figura_fondo":
                run_figura_fondo_test(patient_id, test_key, test_name)

            elif test_key == "acinetopsia":
                run_acinetopsia_test(patient_id, test_key, test_name)

            elif test_key == "estabilizador_trayectoria":
                run_estabilizador_trayectoria_test(patient_id, test_key, test_name)

            elif test_key == "ley_de_fitts":
                run_ley_de_fitts_test(patient_id, test_key, test_name)

            elif test_key == "barrido_ritmico":
                run_barrido_ritmico_test(patient_id, test_key, test_name)

            elif test_key == "arrastre_sostenido":
                run_arrastre_sostenido_test(patient_id, test_key, test_name)

            elif test_key == "reaccion_multimodal":
                run_reaccion_multimodal_test(patient_id, test_key, test_name)

            elif test_key == "ganancia_adaptativa":
                run_ganancia_adaptativa_test(patient_id, test_key, test_name)


            elif test_key == "denominacion_fonologica":
                run_denominacion_fonologica_test(patient_id, test_key, test_name)

            elif test_key == "memoria_n_back":
                run_memoria_n_back_test(patient_id, test_key, test_name)

            elif test_key == "efecto_stroop":
                run_efecto_stroop_test(patient_id, test_key, test_name)

            elif test_key == "completamiento_semantico":
                run_completamiento_semantico_test(patient_id, test_key, test_name)

            elif test_key == "intruso_logico":
                run_intruso_logico_test(patient_id, test_key, test_name)

            elif test_key == "secuenciacion_avd":
                run_secuenciacion_avd_test(patient_id, test_key, test_name)


            else:
                run_pygame_test(patient_id, test_key, test_name)

        finally:
        
            self.root.deiconify()

            if self.current_area_key.get() == "area1":
                    self.build_area1_menu(patient_id)
            elif self.current_area_key.get() == "area2":
                    self.build_area2_menu(patient_id)
            else:
                    self.build_area3_menu(patient_id)


# ============================================================
# PUNTO DE ENTRADA
# ============================================================
def main():
    """
    Función principal del programa.
    Crea la ventana raíz de Tkinter y lanza la app.
    """
    root = tk.Tk()
    app = OpenRehabApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
