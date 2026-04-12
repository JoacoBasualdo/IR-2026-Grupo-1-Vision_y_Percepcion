import os
#Estos import sirven para el guardado de datos
import json
import random
import time
from datetime import datetime
from pathlib import Path

#Estos import son utilizados como interfaces visuales
import tkinter as tk
from tkinter import ttk, messagebox

#Import para reconocer audio
import speech_recognition as sr
from difflib import SequenceMatcher

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
def save_result_json(patient_id: str, test_key: str, metrics_dict: dict, attempts: int):
    """
    Guarda el resultado incluyendo métricas avanzadas (omisiones, latencia, redundancia).
    """
    payload = {
        "id_paciente": patient_id,
        "fecha": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "test": test_key,
        "metricas": metrics_dict, # Ahora es un objeto con múltiples datos
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


def get_metric_summary(result: dict) -> str:
    """
    Devuelve un resumen corto y legible de las métricas para mostrar en historial/comparación.
    """
    metricas = result.get("metricas", {}) or {}

    priority_keys = [
        "correctas", "encontrados", "lat", "val", "tiempo", "porcentaje",
        "om_i", "hits", "desvios", "niveles_superados", "clicks_totales"
    ]
    labels = {
        "correctas": "Correctas",
        "incorrectas": "Incorrectas",
        "encontrados": "Encontrados",
        "no_encontrados": "No encontrados",
        "lat": "Latencia",
        "val": "Validez",
        "tiempo": "Tiempo",
        "tiempo_promedio": "Tiempo prom.",
        "porcentaje": "Acierto",
        "om_i": "Omisiones izq.",
        "om_d": "Omisiones der.",
        "red": "Redundancia",
        "clicks_totales": "Clicks",
        "misclicks": "Misclicks",
        "prec": "Precisión",
        "lect": "Lectura",
        "msg": "Mensaje",
        "rango": "Rango",
    }

    parts = []
    for key in priority_keys:
        if key in metricas:
            value = metricas[key]
            if key == "porcentaje":
                value = f"{value}%"
            elif key in ("tiempo", "tiempo_promedio", "lat", "lect"):
                value = f"{value}s"
            parts.append(f"{labels.get(key, key)}: {value}")
        if len(parts) >= 2:
            break

    if not parts and metricas:
        first_items = list(metricas.items())[:2]
        for key, value in first_items:
            parts.append(f"{labels.get(key, key)}: {value}")

    return " | ".join(parts) if parts else "Sin métricas disponibles"


def build_report_lines(result: dict) -> list[str]:
    """
    Convierte el JSON guardado en una lista de líneas para visualizar como informe.
    """
    metricas = result.get("metricas", {}) or {}
    labels = {
        "correctas": "Figuras correctas",
        "incorrectas": "Figuras incorrectas",
        "total": "Total",
        "tiempo": "Tiempo total",
        "tiempo_promedio": "Tiempo promedio",
        "porcentaje": "Porcentaje de acierto",
        "encontrados": "Objetivos encontrados",
        "no_encontrados": "Objetivos no encontrados",
        "clicks_totales": "Clicks totales",
        "misclicks": "Misclicks",
        "lat": "Latencia al primer hallazgo",
        "om_i": "Omisiones lado izquierdo",
        "om_d": "Omisiones lado derecho",
        "red": "Redundancia",
        "prec": "Precisión motora",
        "val": "Validez de voz",
        "lect": "Tiempo de lectura",
        "rango": "Rango",
        "msg": "Interpretación",
    }

    lines = [
        f"Paciente: {result.get('id_paciente', '-')}",
        f"Fecha: {result.get('fecha', '-')}",
        f"Test: {result.get('test', '-')}",
        ""
    ]

    for key, value in metricas.items():
        if key == "tiempo_maximo":
            continue
        if key == "porcentaje":
            display = f"{value}%"
        elif key in ("tiempo", "tiempo_promedio", "lat", "lect"):
            display = f"{value}s"
        elif key == "val":
            display = f"{value}%"
        else:
            display = value
        lines.append(f"{labels.get(key, key)}: {display}")

    if len(lines) == 4:
        lines.append("No hay métricas detalladas disponibles para este resultado.")

    return lines



OPENREHAB_PYGAME_THEME = {
    "bg_main": (10, 37, 64),
    "bg_band": (16, 47, 78),
    "bg_card": (22, 58, 99),
    "border_card": (43, 92, 136),
    "text_primary": (244, 248, 252),
    "text_secondary": (199, 217, 234),
    "accent_blue": (79, 195, 247),
    "accent_green": (114, 211, 154),
    "accent_green_soft": (139, 227, 174),
    "accent_warning": (255, 214, 102),
}

def _wrap_pygame_text(text, font, max_width):
    words = text.split()
    if not words:
        return [""]
    lines = []
    current = words[0]
    for word in words[1:]:
        test_line = f"{current} {word}"
        if font.size(test_line)[0] <= max_width:
            current = test_line
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines

def _draw_openrehab_shell(screen, width, height):
    theme = OPENREHAB_PYGAME_THEME
    screen.fill(theme["bg_main"])
    pygame.draw.rect(screen, theme["bg_band"], pygame.Rect(0, 0, width, 16), border_radius=0)
    pygame.draw.rect(screen, theme["accent_green_soft"], pygame.Rect(0, height - 10, width, 4), border_radius=0)
    pygame.draw.rect(screen, theme["accent_blue"], pygame.Rect(0, height - 6, width, 6), border_radius=0)

    deco_surface = pygame.Surface((width, height), pygame.SRCALPHA)
    pygame.draw.circle(deco_surface, (255, 255, 255, 18), (width - 140, 120), 90)
    pygame.draw.circle(deco_surface, (255, 255, 255, 10), (100, height - 90), 70)
    pygame.draw.circle(deco_surface, (255, 255, 255, 8), (width - 260, height - 120), 48)
    screen.blit(deco_surface, (0, 0))

def _draw_openrehab_card(screen, rect):
    theme = OPENREHAB_PYGAME_THEME
    shadow_rect = rect.move(8, 10)
    shadow = pygame.Surface((shadow_rect.width, shadow_rect.height), pygame.SRCALPHA)
    pygame.draw.rect(shadow, (0, 0, 0, 70), shadow.get_rect(), border_radius=28)
    screen.blit(shadow, shadow_rect.topleft)

    pygame.draw.rect(screen, theme["bg_card"], rect, border_radius=28)
    pygame.draw.rect(screen, theme["border_card"], rect, 2, border_radius=28)
    pygame.draw.rect(screen, (29, 77, 127), pygame.Rect(rect.x, rect.y, rect.width, 10), border_radius=28)


def draw_openrehab_intro_screen(screen, width, height, test_name, patient_id, instructions, start_text="Presioná ESPACIO para comenzar.", back_text="ESC para volver al menú.", badge_text=None):
    theme = OPENREHAB_PYGAME_THEME
    _draw_openrehab_shell(screen, width, height)

    title_font = pygame.font.SysFont("arial", 34, bold=True)
    subtitle_font = pygame.font.SysFont("arial", 22)
    body_font = pygame.font.SysFont("arial", 34)
    small_font = pygame.font.SysFont("arial", 20)
    button_font = pygame.font.SysFont("arial", 22, bold=True)

    header_x = 72
    screen.blit(title_font.render("OpenRehab ACV", True, theme["text_primary"]), (header_x, 46))
    screen.blit(subtitle_font.render("Evaluación interactiva", True, theme["text_secondary"]), (header_x, 88))
    screen.blit(title_font.render(test_name, True, theme["text_primary"]), (header_x, 138))

    card = pygame.Rect(64, 208, width - 128, height - 292)
    _draw_openrehab_card(screen, card)

    if badge_text:
        badge_rect = pygame.Rect(card.x + 34, card.y + 34, 230, 42)
        pygame.draw.rect(screen, (36, 72, 110), badge_rect, border_radius=20)
        pygame.draw.rect(screen, theme["border_card"], badge_rect, 1, border_radius=20)
        badge_surface = small_font.render(badge_text, True, theme["text_primary"])
        screen.blit(badge_surface, (badge_rect.x + 18, badge_rect.y + 10))

    patient_rect = pygame.Rect(card.right - 300, card.y + 34, 260, 42)
    pygame.draw.rect(screen, (36, 72, 110), patient_rect, border_radius=20)
    pygame.draw.rect(screen, theme["border_card"], patient_rect, 1, border_radius=20)
    patient_surface = small_font.render(f"Paciente: {patient_id}", True, theme["accent_warning"])
    screen.blit(patient_surface, (patient_rect.x + 16, patient_rect.y + 10))

    current_y = card.y + 140
    max_width = card.width - 120

    for line in instructions:
        wrapped = _wrap_pygame_text(line, body_font, max_width)
        for wrapped_line in wrapped:
            text_surface = body_font.render(wrapped_line, True, theme["text_secondary"])
            text_rect = text_surface.get_rect(center=(width // 2, current_y))
            screen.blit(text_surface, text_rect)
            current_y += 42
        current_y += 10

    button_rect = pygame.Rect(card.x + 42, card.bottom - 106, 390, 56)
    pygame.draw.rect(screen, theme["accent_green"], button_rect, border_radius=18)
    button_text = button_font.render(start_text, True, (10, 37, 64))
    text_rect = button_text.get_rect(center=button_rect.center)
    screen.blit(button_text, text_rect)

    back_surface = small_font.render(back_text, True, theme["text_secondary"])
    screen.blit(back_surface, (card.x + 42, card.bottom - 38))

def draw_openrehab_result_screen(screen, width, height, test_name, summary_lines, action_text="ENTER para volver al menú", secondary_text="ESC para salir", title="Test finalizado", badge_text="Resultado"):
    theme = OPENREHAB_PYGAME_THEME
    _draw_openrehab_shell(screen, width, height)

    title_font = pygame.font.SysFont("arial", 34, bold=True)
    subtitle_font = pygame.font.SysFont("arial", 22)
    body_font = pygame.font.SysFont("arial", 24)
    small_font = pygame.font.SysFont("arial", 20)
    button_font = pygame.font.SysFont("arial", 22, bold=True)

    header_x = 72
    screen.blit(title_font.render("OpenRehab ACV", True, theme["text_primary"]), (header_x, 46))
    screen.blit(subtitle_font.render("Resumen del test", True, theme["text_secondary"]), (header_x, 88))
    screen.blit(title_font.render(test_name, True, theme["text_primary"]), (header_x, 138))

    card = pygame.Rect(64, 208, width - 128, height - 292)
    _draw_openrehab_card(screen, card)

    badge_rect = pygame.Rect(card.x + 34, card.y + 34, 190, 42)
    pygame.draw.rect(screen, (36, 72, 110), badge_rect, border_radius=20)
    pygame.draw.rect(screen, theme["border_card"], badge_rect, 1, border_radius=20)
    screen.blit(small_font.render(badge_text, True, theme["text_primary"]), (badge_rect.x + 18, badge_rect.y + 10))

    status_surface = title_font.render(title, True, theme["accent_green_soft"])
    screen.blit(status_surface, (card.x + 40, card.y + 96))

    current_y = card.y + 168
    max_width = card.width - 84
    for line in summary_lines:
        for wrapped_line in _wrap_pygame_text(line, body_font, max_width):
            screen.blit(body_font.render(wrapped_line, True, theme["text_secondary"]), (card.x + 42, current_y))
            current_y += 34
        current_y += 10

    button_rect = pygame.Rect(card.x + 42, card.bottom - 106, 340, 56)
    pygame.draw.rect(screen, theme["accent_blue"], button_rect, border_radius=18)
    button_text = button_font.render(action_text, True, (244, 248, 252))
    screen.blit(button_text, button_text.get_rect(center=button_rect.center))

    secondary_surface = small_font.render(secondary_text, True, theme["text_secondary"])
    screen.blit(secondary_surface, (card.x + 42, card.bottom - 38))

# --- FUNCIÓN DE RECONOCIMIENTO DE VOZ ---
# --- FUNCIÓN DE VOZ OPTIMIZADA (EVITA CONGELAMIENTO) ---
def procesar_voz(frase_objetivo):
    recognizer = sr.Recognizer()
    # Reducimos drásticamente los tiempos para que no se trabe el juego [cite: 107, 109]
    try:
        with sr.Microphone() as source:
            # Ajuste de ruido ultra rápido
            recognizer.adjust_for_ambient_noise(source, duration=0.3)
            # Solo espera 3 segundos. Si el paciente no empieza a hablar, sigue de largo.
            audio = recognizer.listen(source, timeout=3, phrase_time_limit=5)
        
        # Intenta reconocer el texto
        texto_dicho = recognizer.recognize_google(audio, language="es-ES")
        similitud = SequenceMatcher(None, frase_objetivo.lower(), texto_dicho.lower()).ratio()
        return round(similitud * 100, 1)
    except Exception as e:
        # Si hay error (silencio, internet, etc), devuelve 0 y NO se traba
        print(f"Aviso: No se procesó voz ({e})")
        return 0.0

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
        draw_openrehab_intro_screen(
            screen,
            width,
            height,
            test_name,
            patient_id,
            [
                "Demo base del test.",
                "Instrucción demo: hacé click sobre los círculos visibles.",
            ],
            start_text="ESPACIO para comenzar",
            back_text="ESC para salir y volver al menú",
            badge_text="Modo demostración",
        )

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
        summary_lines = [
            f"Métrica principal: {final_metric} {final_unit}",
            f"Errores registrados: {misses}",
        ]
        if saved_path:
            summary_lines.append(f"Archivo guardado: {saved_path}")
        draw_openrehab_result_screen(
            screen,
            width,
            height,
            test_name,
            summary_lines,
            action_text="ENTER para volver al menú",
            secondary_text="ESC para salir",
            title="Resultado guardado",
            badge_text="Guardado exitoso",
        )

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
                    metrics_dict={"aciertos": final_metric, "errores": misses},
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


import pygame
import random

# --- CLASE AUXILIAR PARA BOTONES INTERACTIVOS ---
class Button:
    def __init__(self, x, y, w, h, text, color, hover_color):
        self.rect = pygame.Rect(x, y, w, h)
        self.text = text
        self.color = color
        self.hover_color = hover_color
        self.is_hovered = False

    def draw(self, screen, font):
        color = self.hover_color if self.is_hovered else self.color
        pygame.draw.rect(screen, color, self.rect, border_radius=10)
        pygame.draw.rect(screen, (255, 255, 255), self.rect, 2, border_radius=10)
        
        text_surf = font.render(self.text, True, (255, 255, 255))
        text_rect = text_surf.get_rect(center=self.rect.center)
        screen.blit(text_surf, text_rect)

    def check_hover(self, mouse_pos):
        self.is_hovered = self.rect.collidepoint(mouse_pos)
        return self.is_hovered

def run_exploracion_faro_test(patient_id: str, test_key: str, test_name: str, difficulty: int):
    # --- 1. CONFIGURACIÓN DE DIFICULTAD Y CONTRASTE ---
    if difficulty == 1: # FÁCIL
        duration_seconds, f_radius, t_radius, total_objects = 60, 180, 40, 10
        color_bg, color_target_unfound = (0, 0, 0), (255, 255, 255) # Contraste Máximo
    elif difficulty == 2: # MEDIO
        duration_seconds, f_radius, t_radius, total_objects = 45, 120, 25, 16
        color_bg, color_target_unfound = (20, 35, 55), (120, 140, 160)
    else: # DIFÍCIL
        duration_seconds, f_radius, t_radius, total_objects = 30, 85, 18, 22
        color_bg, color_target_unfound = (45, 45, 45), (52, 52, 52) # Contraste Mínimo

    pygame.init()
    width, height = 1200, 750
    screen = pygame.display.set_mode((width, height))
    pygame.display.set_caption(f"{APP_TITLE} - {test_name}")
    clock = pygame.time.Clock()
    
    # Fuentes con la estética de la App
    font_hud = pygame.font.SysFont("arial", 26, bold=True)
    font_giant = pygame.font.SysFont("arial", 90, bold=True)
    font_button = pygame.font.SysFont("arial", 24, bold=True)
    font_report = pygame.font.SysFont("arial", 22)

    # --- 2. VARIABLES DE ESTADO Y MÉTRICAS ---
    state = "intro"
    show_report = False
    start_ticks = None
    first_hit_ticks = None 
    found_count = 0
    redundancy_accum = 0
    last_side = None
    final_metrics = {}

    # Generación de estímulos (Balance para evaluar Neglect) [cite: 85]
    objects = []
    for i in range(total_objects):
        side = "left" if i < total_objects // 2 else "right"
        margin = t_radius + 30
        x_min = margin if side == "left" else width // 2 + margin
        x_max = width // 2 - margin if side == "left" else width - margin
        objects.append({
            "x": random.randint(x_min, x_max),
            "y": random.randint(150, height - margin),
            "r": t_radius, "found": False, "side": side
        })

    # --- 3. DEFINICIÓN DE BOTONES ---
    btn_reporte = pygame.Rect(width // 2 - 220, height - 130, 210, 55)
    btn_volver = pygame.Rect(width // 2 + 10, height - 130, 210, 55)
    btn_cerrar = pygame.Rect(width // 2 - 100, 560, 200, 45)

    running = True
    while running:
        screen.fill(color_bg)
        mx, my = pygame.mouse.get_pos()

        for event in pygame.event.get():
            if event.type == pygame.QUIT: running = False
            
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE: running = False
                if state == "intro" and event.key == pygame.K_SPACE:
                    state = "playing"
                    start_ticks = pygame.time.get_ticks()
                elif state == "result" and event.key == pygame.K_RETURN and not show_report:
                    running = False

            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if state == "playing":
                    for obj in objects:
                        if not obj["found"]:
                            dist = ((mx - obj["x"])**2 + (my - obj["y"])**2)**0.5
                            if dist <= obj["r"]:
                                obj["found"] = True
                                found_count += 1
                                if found_count == 1: first_hit_ticks = pygame.time.get_ticks()
                                break
                elif state == "result":
                    if btn_reporte.collidepoint(mx, my) and not show_report:
                        show_report = True
                    elif btn_volver.collidepoint(mx, my) and not show_report:
                        running = False
                    elif btn_cerrar.collidepoint(mx, my) and show_report:
                        show_report = False

        # --- LÓGICA DE RENDERIZADO ---
        if state == "intro":
            draw_openrehab_intro_screen(screen, width, height, test_name, patient_id, 
                ["Explorá toda la pantalla con tu linterna.", "Encontrá los objetos ocultos para mejorar tu visión."], 
                "ESPACIO para comenzar", "ESC para salir", f"Nivel {difficulty}")

        elif state == "playing":
            elapsed = (pygame.time.get_ticks() - start_ticks) / 1000
            remaining = max(0, duration_seconds - elapsed)

            # Redundancia: cruces de mirada para evaluar memoria de trabajo [cite: 41, 42]
            current_side = "L" if mx < width/2 else "R"
            if last_side and current_side != last_side: redundancy_accum += 1
            last_side = current_side

            for obj in objects:
                dist = ((mx - obj["x"])**2 + (my - obj["y"])**2)**0.5
                if obj["found"]:
                    pygame.draw.circle(screen, (114, 211, 154), (obj["x"], obj["y"]), obj["r"])
                elif dist <= f_radius:
                    pygame.draw.circle(screen, color_target_unfound, (obj["x"], obj["y"]), obj["r"])

            # Capa de oscuridad estética
            darkness = pygame.Surface((width, height), pygame.SRCALPHA)
            darkness.fill((10, 37, 64, 252)) # Azul OpenRehab
            pygame.draw.circle(darkness, (0, 0, 0, 0), (mx, my), f_radius)
            screen.blit(darkness, (0, 0))
            pygame.draw.circle(screen, (79, 195, 247), (mx, my), f_radius, 3) # Borde azul celeste

            # HUD
            screen.blit(font_hud.render(f"Tiempo: {int(remaining)}s", True, (255, 214, 102)), (width - 180, 35))
            screen.blit(font_hud.render(f"Objetivos: {found_count}/{total_objects}", True, (244, 248, 252)), (40, 35))

            if found_count == total_objects or remaining <= 0:
                # Métricas diagnósticas [cite: 31, 37, 39, 41]
                lat = (first_hit_ticks - start_ticks)/1000 if first_hit_ticks else elapsed
                om_i = sum(1 for o in objects if not o["found"] and o["side"] == "left")
                om_d = sum(1 for o in objects if not o["found"] and o["side"] == "right")
                eficiencia = found_count / elapsed if elapsed > 0 else 0
                porc = (found_count / total_objects) * 100

                # Feedback Motivante
                if porc >= 90:
                    msg, rango = "¡Excelente rendimiento! Dominio visual total.", "EXCELENTE"
                elif porc >= 60:
                    msg, rango = "¡Muy bien! Estás ampliando tu campo visual con éxito.", "BIEN HECHO"
                else:
                    msg = "¡Buen esfuerzo! Intentá explorar más el lado izquierdo." if om_i > om_d else "¡Seguí practicando! Tu persistencia dará frutos."
                    rango = "SIGUE ASÍ"

                final_metrics = {"lat": round(lat, 2), "om_i": om_i, "om_d": om_d, "red": redundancy_accum // 2, "msg": msg, "rango": rango}
                save_result_json(patient_id, test_key, final_metrics, 1)
                state = "result"

        elif state == "result":
            screen.fill((10, 37, 64)) # Fondo azul marca
            
            if not show_report:
                # Pantalla de Rango Gigante
                txt_surf = font_giant.render(final_metrics["rango"], True, (114, 211, 154))
                screen.blit(txt_surf, (width//2 - txt_surf.get_width()//2, 220))
                
                msg_surf = font_hud.render(final_metrics["msg"], True, (199, 217, 234))
                screen.blit(msg_surf, (width//2 - msg_surf.get_width()//2, 340))

                # Dibujar Botones
                for b, txt, col in [(btn_reporte, "VER INFORME", (79, 195, 247)), (btn_volver, "VOLVER", (36, 72, 110))]:
                    pygame.draw.rect(screen, col, b, border_radius=12)
                    t_s = font_button.render(txt, True, (255, 255, 255))
                    screen.blit(t_s, t_s.get_rect(center=b.center))
            else:
                # Pop-up de Informe Médico Detallado [cite: 36]
                pygame.draw.rect(screen, (244, 248, 252), (width//2 - 300, 150, 600, 480), border_radius=20)
                pygame.draw.rect(screen, (43, 92, 136), (width//2 - 300, 150, 600, 480), 3, border_radius=20)
                
                t_rep = font_button.render("INFORME CLÍNICO DETALLADO", True, (10, 37, 64))
                screen.blit(t_rep, (width//2 - t_rep.get_width()//2, 180))
                
                info_lines = [
                    f"Latencia al primer hallazgo: {final_metrics['lat']}s",
                    f"Omisiones Lado Izquierdo: {final_metrics['om_i']}",
                    f"Omisiones Lado Derecho: {final_metrics['om_d']}",
                    f"Redundancia (Cruces de línea media): {final_metrics['red']}",
                    f"Efectividad de rastreo: {int((found_count/total_objects)*100)}%"
                ]
                for i, line in enumerate(info_lines):
                    l_s = font_report.render(line, True, (36, 72, 110))
                    screen.blit(l_s, (width//2 - 240, 260 + (i * 45)))

                pygame.draw.rect(screen, (180, 50, 50), btn_cerrar, border_radius=10)
                c_s = font_button.render("CERRAR", True, (255, 255, 255))
                screen.blit(c_s, c_s.get_rect(center=btn_cerrar.center))

        pygame.display.flip()
        clock.tick(60)
    pygame.quit()
    

def run_anclaje_visual_test(patient_id: str, test_key: str, test_name: str, difficulty: int):
    # --- CONFIGURACIÓN DE NIVELES Y FRASES OPTIMIZADAS ---
    if difficulty == 1: # FÁCIL
        ancla_w, blink_speed, area_tolerancia, mov_x, mov_y = 65, 450, 45, 0, 0
        frases = [
            "El sol sale por el este.", 
            "El gato toma leche fresca.", 
            "La casa es de color azul.",
            "Hoy es un día despejado."
        ] # [cite: 54, 57]
    elif difficulty == 2: # MEDIO
        ancla_w, blink_speed, area_tolerancia, mov_x, mov_y = 35, 750, 25, 40, 80
        frases = [
            "La corteza cerebral procesa la información sensorial compleja.",
            "El hemisferio derecho coordina la orientación espacial del cuerpo.",
            "La plasticidad neuronal permite la recuperación de funciones perdidas.",
            "La atención sostenida es vital para completar tareas cotidianas."
        ] # [cite: 60, 63]
    else: # DIFÍCIL
        ancla_w, blink_speed, area_tolerancia, mov_x, mov_y = 15, 0, 8, 100, 220
        frases = [
            "La heminegligencia espacial resulta de lesiones en el lóbulo parietal posterior.",
            "El sistema de activación reticular influye en el estado de alerta del paciente.",
            "Los movimientos sacádicos permiten desplazar el foco atencional rápidamente.",
            "La decodificación fonológica integra áreas visuales y auditivas del lenguaje."
        ] # [cite: 66, 69]

    pygame.init()
    width, height = 1200, 750
    screen = pygame.display.set_mode((width, height))
    clock = pygame.time.Clock()

    # Fuentes y Botones
    font_text = pygame.font.SysFont("arial", 30)
    font_hud = pygame.font.SysFont("arial", 26, bold=True)
    font_giant = pygame.font.SysFont("arial", 90, bold=True)
    font_button = pygame.font.SysFont("arial", 24, bold=True)
    font_report = pygame.font.SysFont("arial", 22)

    state = "intro"
    show_report = False
    current_idx = 0
    # Posición inicial del ancla
    ancla_x, ancla_y = 15, 200 
    
    latencias, precisiones, tiempos_lectura, validez_vocal = [], [], [], []
    final_metrics = {}

    btn_reporte = pygame.Rect(width // 2 - 220, height - 130, 210, 55)
    btn_volver = pygame.Rect(width // 2 + 10, height - 130, 210, 55)
    btn_cerrar = pygame.Rect(width // 2 - 100, 560, 200, 45)

    running = True
    while running:
        screen.fill((10, 37, 64)) 
        mx, my = pygame.mouse.get_pos()
        t_now = pygame.time.get_ticks()

        for event in pygame.event.get():
            if event.type == pygame.QUIT: running = False
            if event.type == pygame.KEYDOWN:
                if state == "intro" and event.key == pygame.K_SPACE:
                    state = "waiting_anchor"
                    start_ancla_time = t_now
                elif state == "result" and event.key == pygame.K_RETURN:
                    running = False

            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if state == "waiting_anchor":
                    ancla_rect = pygame.Rect(ancla_x, ancla_y, ancla_w, 350)
                    colision = ancla_rect.inflate(area_tolerancia, area_tolerancia)
                    if colision.collidepoint(event.pos):
                        latencias.append((t_now - start_ancla_time) / 1000)
                        dist = ((event.pos[0]-ancla_rect.centerx)**2 + (event.pos[1]-ancla_rect.centery)**2)**0.5
                        precisiones.append(dist)
                        state = "reading"
                        start_lectura_time = t_now
                elif state == "result":
                    if btn_reporte.collidepoint(mx, my): show_report = True
                    elif btn_volver.collidepoint(mx, my): running = False
                    elif btn_cerrar.collidepoint(mx, my): show_report = False

        # --- RENDERIZADO DE ESTADOS ---
        if state == "intro":
            draw_openrehab_intro_screen(screen, width, height, test_name, patient_id, 
                ["Escanea el borde izquierdo para habilitar la lectura.", "Lee las frases técnicas en voz alta."], 
                "ESPACIO para comenzar", "ESC para salir", f"Nivel {difficulty}")

        elif state == "waiting_anchor":
            # Ancla dinámica en X e Y (siempre sector izquierdo)
            if blink_speed == 0 or (t_now // blink_speed) % 2 == 0:
                pygame.draw.rect(screen, (220, 20, 20), (ancla_x, ancla_y, ancla_w, 350), border_radius=8)

        elif state == "reading":
            screen.fill((244, 248, 252))
            pygame.draw.rect(screen, (220, 20, 20), (ancla_x, ancla_y, ancla_w, 350)) 
            txt_surf = font_text.render(frases[current_idx], True, (10, 37, 64))
            screen.blit(txt_surf, (200, height//2))
            screen.blit(font_hud.render("SISTEMA DE AUDIO ACTIVO - Lee ahora", True, (200, 30, 30)), (400, 600))
            pygame.display.flip()
            
            validez = procesar_voz(frases[current_idx])
            validez_vocal.append(validez)
            tiempos_lectura.append((pygame.time.get_ticks() - start_lectura_time) / 1000)
            
            current_idx += 1
            if current_idx >= len(frases):
                # Cálculos finales
                avg_lat = round(sum(latencias)/len(latencias), 2)
                avg_prec = round(sum(precisiones)/len(precisiones), 1)
                avg_val = round(sum(validez_vocal)/len(validez_vocal), 1)
                avg_lect = round(sum(tiempos_lectura)/len(tiempos_lectura), 1)
                
                rango = "EXCELENTE!" if avg_val > 80 else ("BIEN HECHO" if avg_val > 60 else "PUEDES SEGUIR MEJORANDO")
                final_metrics = {"lat": avg_lat, "prec": avg_prec, "val": avg_val, "lect": avg_lect, "rango": rango}
                save_result_json(patient_id, test_key, final_metrics, 1)
                state = "result"
            else:
                # Movimiento horizontal y vertical restringido a la izquierda [cite: 73]
                ancla_x = random.randint(10, 10 + mov_x)
                ancla_y = random.randint(50, 50 + mov_y)
                state = "waiting_anchor"
                start_ancla_time = pygame.time.get_ticks()

        elif state == "result":
            if not show_report:
                txt_surf = font_giant.render(final_metrics["rango"], True, (114, 211, 154))
                screen.blit(txt_surf, (width//2 - txt_surf.get_width()//2, 220))
                pygame.draw.rect(screen, (79, 195, 247), btn_reporte, border_radius=12)
                screen.blit(font_button.render("VER INFORME", True, (255, 255, 255)), font_button.render("VER INFORME", True, (255, 255, 255)).get_rect(center=btn_reporte.center))
                pygame.draw.rect(screen, (36, 72, 110), btn_volver, border_radius=12)
                screen.blit(font_button.render("VOLVER", True, (255, 255, 255)), font_button.render("VOLVER", True, (255, 255, 255)).get_rect(center=btn_volver.center))
            else:
                pygame.draw.rect(screen, (244, 248, 252), (width//2 - 300, 150, 600, 480), border_radius=20)
                info = [
                    f"Latencia activación: {final_metrics['lat']}s",
                    f"Precisión motora: {final_metrics['prec']} px",
                    f"Tiempo lectura: {final_metrics['lect']}s",
                    f"Validez de voz: {final_metrics['val']}%"
                ]
                for i, line in enumerate(info):
                    screen.blit(font_report.render(line, True, (36, 72, 110)), (width//2 - 240, 270 + (i * 50)))
                pygame.draw.rect(screen, (180, 50, 50), btn_cerrar, border_radius=10)
                screen.blit(font_button.render("CERRAR", True, (255, 255, 255)), font_button.render("CERRAR", True, (255, 255, 255)).get_rect(center=btn_cerrar.center))

        pygame.display.flip()
        clock.tick(60)
    pygame.quit()
    
def run_complejidad_gradual_test(patient_id: str, test_key: str, test_name: str, difficulty: int):
    
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
    show_report = False
    levels = 6
    current_level = 0
    total_clicks = 0
    start_ticks = None
    start_level_ticks = 0
    round_times = []
    final_metrics = {}

    btn_reporte = pygame.Rect(width // 2 - 220, height - 130, 210, 55)
    btn_volver = pygame.Rect(width // 2 + 10, height - 130, 210, 55)
    btn_cerrar = pygame.Rect(width // 2 - 100, 560, 200, 45)

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

        if difficulty == 1:
            base_cols = 5
            base_rows = 3
        elif difficulty == 2:
            base_cols = 7
            base_rows = 4
        else:
            base_cols = 9
            base_rows = 5

        cols = base_cols + level_index
        rows = base_rows + level_index // 2
        cell_w = min(110, (width - 240) // cols)
        cell_h = min(90, (height - 250) // rows)
        start_x = 120
        start_y = 170

        all_cells = []
        for r in range(rows):
            for c in range(cols):
                x = start_x + c * cell_w
                y = start_y + r * cell_h
                rect_w = int(cell_w * 0.7)
                rect_h = int(cell_h * 0.7)

                all_cells.append(pygame.Rect(x, y, rect_w, rect_h))
                
        random.shuffle(all_cells)
        target_rect = all_cells[0]

        for rect in all_cells[1:]:
            distractor_rects.append(rect)

    generate_level(current_level)
    level_start_time = pygame.time.get_ticks()
    def draw_intro():
        draw_openrehab_intro_screen(
            screen,
            width,
            height,
            test_name,
            patient_id,
            [
                "Encontrá la figura objetivo entre distractores.",
                "La dificultad aumenta en cada nivel.",
            ],
            start_text="ESPACIO para comenzar",
            back_text="ESC para volver al menú",
            badge_text="Área visual",
        )

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
        f_hud = pygame.font.SysFont("arial", 26, bold=True)
        f_giant = pygame.font.SysFont("arial", 80, bold=True)
        f_button = pygame.font.SysFont("arial", 24, bold=True)
        f_report = pygame.font.SysFont("arial", 22)
        
        screen.fill((10, 37, 64)) 

        if not show_report:
            txt_surf = f_giant.render(final_metrics.get("rango", ""), True, (114, 211, 154))
            screen.blit(txt_surf, (width // 2 - txt_surf.get_width() // 2, 220))

            msg_surf = f_hud.render(final_metrics.get("msg", ""), True, (199, 217, 234))
            screen.blit(msg_surf, (width // 2 - msg_surf.get_width() // 2, 340))

            for rect, label, col in [(btn_reporte, "VER INFORME", (79, 195, 247)), (btn_volver, "VOLVER", (36, 72, 110))]:
                pygame.draw.rect(screen, col, rect, border_radius=12)
                t_s = f_button.render(label, True, (255, 255, 255))
                screen.blit(t_s, t_s.get_rect(center=rect.center))
        else:
            p_rect = pygame.Rect(width // 2 - 300, 150, 600, 480)
            pygame.draw.rect(screen, (244, 248, 252), p_rect, border_radius=20)
            pygame.draw.rect(screen, (43, 92, 136), p_rect, 3, border_radius=20)

            t_surf = f_button.render("INFORME DE COMPLEJIDAD GRADUAL", True, (10, 37, 64))
            screen.blit(t_surf, (width // 2 - t_surf.get_width() // 2, 180))

            # Las métricas que pediste:
            lines = [
                f"Tiempo Total de Prueba: {final_metrics.get('tiempo_total')}s",
                f"Tiempo Reacción Promedio: {final_metrics.get('reaccion_promedio')}s",
                f"Variación (Nivel 1 vs Final): {final_metrics.get('variacion_reaccion')}s",
                f"Porcentaje Clicks Acertados: {final_metrics.get('porcentaje_acierto')}%",
                f"Niveles Superados: 6/6"
            ]
            for i, line in enumerate(lines):
                l_surf = f_report.render(line, True, (36, 72, 110))
                screen.blit(l_surf, (width // 2 - 230, 260 + (i * 50)))

            pygame.draw.rect(screen, (180, 50, 50), btn_cerrar, border_radius=10)
            c_surf = f_button.render("CERRAR", True, (255, 255, 255))
            screen.blit(c_surf, c_surf.get_rect(center=btn_cerrar.center))
            
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
                    show_report = False
                    total_clicks = 0
                    round_times = []
                    start_ticks = pygame.time.get_ticks()
                    start_level_ticks = pygame.time.get_ticks()

                elif state == "result" and event.key == pygame.K_RETURN and not show_report:
                    running = False

            elif event.type == pygame.MOUSEBUTTONDOWN:
                mx, my = event.pos
                if state == "playing":
                    total_clicks += 1
                    if target_rect.collidepoint(mx, my):
                        ahora = pygame.time.get_ticks()
                        duracion_nivel = (ahora - start_level_ticks) / 1000
                        round_times.append(duracion_nivel)
                        start_level_ticks = ahora
                        current_level += 1

                        if current_level >= levels:
                            tiempo_total = (pygame.time.get_ticks() - start_ticks) / 1000
                            avg_reaccion = round(tiempo_total / 6, 2)
                            variacion = round(round_times[-1] - round_times[0], 2)
                            porcentaje_acierto = round((6 / total_clicks) * 100, 1) if total_clicks > 0 else 0
                        
                            if porcentaje_acierto > 85: rango, msg = "EXCELENTE", "Gran precisión y velocidad de procesamiento visual."
                            elif porcentaje_acierto > 60: rango, msg = "MUY BIEN", "Buen desempeño en la búsqueda de objetivos."
                            else: rango, msg = "SIGUE ASÍ", "La práctica constante mejorará tu atención selectiva."

                            final_metrics = {
                                "tiempo_total": round(tiempo_total, 2),
                                "reaccion_promedio": avg_reaccion,
                                "variacion_reaccion": variacion,
                                "porcentaje_acierto": porcentaje_acierto,
                                "rango": rango,
                                "msg": msg
                            }
                            save_result_json(patient_id, test_key, final_metrics, attempts)
                            state = "result"
                        else:
                            generate_level(current_level)

                elif state == "result":
                    if btn_reporte.collidepoint(mx, my) and not show_report:
                        show_report = True
                    elif btn_volver.collidepoint(mx, my) and not show_report:
                        running = False
                    elif btn_cerrar.collidepoint(mx, my) and show_report:
                        show_report = False

        if state == "intro":
            draw_intro()
        elif state == "playing":
            draw_playing()
        elif state == "result":
            draw_result()

        pygame.display.flip()
        clock.tick(60)

    pygame.quit()

def run_cancelacion_estimulos_test(patient_id: str, test_key: str, test_name: str, difficulty: int):
    
    pygame.init()

    width, height = 1200, 760
    screen = pygame.display.set_mode((width, height))
    pygame.display.set_caption(f"{APP_TITLE} - {test_name}")

    clock = pygame.time.Clock()
    font       = pygame.font.SysFont("arial", 24)
    cell_font  = pygame.font.SysFont("arial", 34, bold=True)
    f_button   = pygame.font.SysFont("arial", 24, bold=True)
    f_report   = pygame.font.SysFont("arial", 22)
    f_giant    = pygame.font.SysFont("arial", 72, bold=True)


   # ── CONFIGURACIÓN POR DIFICULTAD ─────────────────────────────────────────
    rows = 7
    cols = 10

    if difficulty == 1:
        targets_goal = 28
    elif difficulty == 2:
        targets_goal = 24
    else:
        targets_goal = 18

    cell_size = 70
    start_x   = (width - cols * cell_size) // 2
    start_y   = 150

    # Botones pantalla resultado (igual que complejidad gradual)
    btn_reporte = pygame.Rect(width // 2 - 220, height - 130, 210, 55)
    btn_volver  = pygame.Rect(width // 2 + 10,  height - 130, 210, 55)
    btn_cerrar  = pygame.Rect(width // 2 - 100, 560, 200, 45)

    # ── ESTADO ───────────────────────────────────────────────────────────────
    state         = "intro"
    attempts      = 1
    show_report   = False
    grid          = []
    total_targets = 0
    found_targets = 0
    wrong_clicks  = 0
    start_time    = None
    final_metrics = {}

    # ── GENERACIÓN DE GRILLA ─────────────────────────────────────────────────
    def generate_grid():
        nonlocal grid, total_targets

        # Crear lista de celdas: primero N targets, luego el resto distractores
        total_cells = rows * cols
        target_count = min(targets_goal, total_cells)
        symbols = ["X"] * target_count + ["O"] * (total_cells - target_count)
        random.shuffle(symbols)

        grid = []
        total_targets = 0
        idx = 0
        for r in range(rows):
            row = []
            for c in range(cols):
                symbol = symbols[idx]; idx += 1
                if symbol == "X":
                    total_targets += 1
                rect = pygame.Rect(
                    start_x + c * cell_size,
                    start_y + r * cell_size,
                    cell_size - 8,
                    cell_size - 8,
                )
                row.append({"symbol": symbol, "clicked": False, "rect": rect})
            grid.append(row)

    generate_grid()

    # ── MÉTRICAS ─────────────────────────────────────────────────────────────
    def compute_metrics():
        tiempo_total = round(time.time() - start_time, 2)
        tiempo_prom  = round(tiempo_total / found_targets, 2) if found_targets > 0 else 0

        if wrong_clicks == 0:
            proporcion = f"{found_targets} / 0  (sin errores)"
        else:
            ratio      = round(found_targets / wrong_clicks, 2)
            proporcion = f"{found_targets} / {wrong_clicks}  (ratio {ratio})"

        total_clicks = found_targets + wrong_clicks
        porcentaje   = round((found_targets / total_clicks) * 100, 1) if total_clicks > 0 else 100.0

        if porcentaje >= 90:
            rango, msg = "EXCELENTE", "Muy alta precisión en la cancelación de estímulos."
        elif porcentaje >= 70:
            rango, msg = "MUY BIEN", "Buen desempeño en la identificación de objetivos."
        else:
            rango, msg = "SIGUE ASÍ", "La práctica mejorará tu atención selectiva."

        return {
            "dificultad":               difficulty,
            "objetivos_encontrados":    found_targets,
            "total_objetivos":          total_targets,
            "clicks_erroneos":          wrong_clicks,
            "tiempo_total":             tiempo_total,
            "proporcion_acierto_error": proporcion,
            "tiempo_promedio_objetivo": tiempo_prom,
            "porcentaje_acierto":       porcentaje,
            "rango":                    rango,
            "msg":                      msg,
        }

    # ── PANTALLAS ─────────────────────────────────────────────────────────────
    def draw_intro():
        # Sin mención de dificultad en las instrucciones
        draw_openrehab_intro_screen(
            screen, width, height, test_name, patient_id,
            ["Hacé click en todas las X de la matriz."],
            start_text="ESPACIO para comenzar",
            back_text="ESC para volver al menú",
            badge_text="Atención selectiva",
        )

    def draw_playing():
        screen.fill((245, 245, 245))
        pygame.draw.rect(screen, (30, 30, 30), pygame.Rect(0, 0, width, 90))

        h1 = font.render(
            f"Encontrados: {found_targets}/{total_targets}  |  Errores: {wrong_clicks}",
            True, (255, 255, 255)
        )
        h2 = font.render("Objetivo: clickeá todas las X", True, (255, 230, 120))
        screen.blit(h1, (20, 18))
        screen.blit(h2, (20, 54))

        for row in grid:
            for cell in row:
                if cell["clicked"] and cell["symbol"] == "X":
                    color = (140, 220, 140)
                elif cell["clicked"] and cell["symbol"] != "X":
                    color = (235, 140, 140)
                else:
                    color = (230, 230, 230)

                pygame.draw.rect(screen, color,        cell["rect"], border_radius=8)
                pygame.draw.rect(screen, (50, 50, 50), cell["rect"], 2, border_radius=8)

                txt = cell_font.render(cell["symbol"], True, (20, 20, 20))
                screen.blit(txt, (cell["rect"].x + 20, cell["rect"].y + 10))

    def draw_result():
        screen.fill((10, 37, 64))

        if not show_report:
            # ── Vista resumen ────────────────────────────────────────────────
            rango_surf = f_giant.render(final_metrics.get("rango", ""), True, (114, 211, 154))
            screen.blit(rango_surf, (width // 2 - rango_surf.get_width() // 2, 200))

            msg_surf = font.render(final_metrics.get("msg", ""), True, (199, 217, 234))
            screen.blit(msg_surf, (width // 2 - msg_surf.get_width() // 2, 310))

            for rect, label, col in [
                (btn_reporte, "VER INFORME", (79, 195, 247)),
                (btn_volver,  "VOLVER",      (36, 72, 110)),
            ]:
                pygame.draw.rect(screen, col, rect, border_radius=12)
                t = f_button.render(label, True, (255, 255, 255))
                screen.blit(t, t.get_rect(center=rect.center))

        else:
            # ── Vista informe detallado ──────────────────────────────────────
            p_rect = pygame.Rect(width // 2 - 320, 120, 640, 500)
            pygame.draw.rect(screen, (244, 248, 252), p_rect, border_radius=20)
            pygame.draw.rect(screen, (43, 92, 136),   p_rect, 3, border_radius=20)

            title_surf = f_button.render("INFORME — CANCELACIÓN DE ESTÍMULOS", True, (10, 37, 64))
            screen.blit(title_surf, (width // 2 - title_surf.get_width() // 2, 150))

            lines = [
                f"Dificultad: {final_metrics.get('dificultad', '-')}",
                f"Objetivos encontrados: {final_metrics.get('objetivos_encontrados', 0)} / {final_metrics.get('total_objetivos', 0)}",
                f"Clicks erróneos: {final_metrics.get('clicks_erroneos', 0)}",
                f"Tiempo de compleción: {final_metrics.get('tiempo_total', 0)}s",
                f"Aciertos / Errores: {final_metrics.get('proporcion_acierto_error', '-')}",
                f"Tiempo promedio por objetivo: {final_metrics.get('tiempo_promedio_objetivo', 0)}s",
                f"Porcentaje de acierto: {final_metrics.get('porcentaje_acierto', 0)}%",
            ]
            for i, line in enumerate(lines):
                l_surf = f_report.render(line, True, (36, 72, 110))
                screen.blit(l_surf, (width // 2 - 270, 210 + i * 44))

            pygame.draw.rect(screen, (180, 50, 50), btn_cerrar, border_radius=10)
            c_surf = f_button.render("CERRAR", True, (255, 255, 255))
            screen.blit(c_surf, c_surf.get_rect(center=btn_cerrar.center))

    # ── LOOP PRINCIPAL ────────────────────────────────────────────────────────
    running = True
    while running:
        for event in pygame.event.get():

            if event.type == pygame.QUIT:
                running = False

            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif state == "intro" and event.key == pygame.K_SPACE:
                    state      = "playing"
                    start_time = time.time()
                elif state == "result" and event.key == pygame.K_RETURN and not show_report:
                    running = False

            elif event.type == pygame.MOUSEBUTTONDOWN:
                mx, my = event.pos

                if state == "playing":
                    for row in grid:
                        for cell in row:
                            if cell["rect"].collidepoint(mx, my) and not cell["clicked"]:
                                cell["clicked"] = True
                                if cell["symbol"] == "X":
                                    found_targets += 1
                                else:
                                    wrong_clicks += 1

                elif state == "result":
                    if btn_reporte.collidepoint(mx, my) and not show_report:
                        show_report = True
                    elif btn_volver.collidepoint(mx, my) and not show_report:
                        running = False
                    elif btn_cerrar.collidepoint(mx, my) and show_report:
                        show_report = False

        # ── Fin de partida ────────────────────────────────────────────────────
        if state == "playing" and found_targets >= total_targets:
            final_metrics = compute_metrics()
            save_result_json(patient_id, test_key, final_metrics, attempts)
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


def run_figura_fondo_test(patient_id: str, test_key: str, test_name: str, difficulty: int):
    pygame.init()

    width, height = 1200, 750
    screen = pygame.display.set_mode((width, height))
    pygame.display.set_caption(f"{APP_TITLE} - {test_name}")
    clock = pygame.time.Clock()

    font = pygame.font.SysFont("arial", 24)
    font_hud = pygame.font.SysFont("arial", 26, bold=True)
    font_giant = pygame.font.SysFont("arial", 80, bold=True)
    font_button = pygame.font.SysFont("arial", 24, bold=True)
    font_report = pygame.font.SysFont("arial", 22)

    state = "intro"
    show_report = False
    attempts = 1

    rounds = 5
    current_round = 0
    correct_count = 0
    incorrect_count = 0
    start_ticks = None
    total_time = 0.0
    avg_time = 0.0
    final_metrics = {}

    target_rect = pygame.Rect(0, 0, 0, 0)
    buttons = []
    target_shape = "rect"

    btn_reporte = pygame.Rect(width // 2 - 220, height - 130, 210, 55)
    btn_volver = pygame.Rect(width // 2 + 10, height - 130, 210, 55)
    btn_cerrar = pygame.Rect(width // 2 - 100, 560, 200, 45)

    target_shape = "rect"
    
    def generate_round():
        nonlocal target_rect, buttons, target_shape

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
        target_shape = random.choice(["rect", "circle", "triangle"])

    generate_round()

    def get_feedback(correctas, total):
        if correctas == total:
            return "EXCELENTE", "¡Excelente rendimiento! Identificaste correctamente todas las figuras."
        elif correctas == total - 1:
            return "MUY BIEN", "Muy buen trabajo. Solo hubo una identificación incorrecta."
        elif correctas == 3:
            return "BIEN HECHO", "Buen desempeño. Lograste reconocer más de la mitad de las figuras."
        elif correctas == 2:
            return "SIGUE ASÍ", "Vas avanzando. Conviene seguir practicando la discriminación figura-fondo."
        elif correctas == 1:
            return "A PRACTICAR", "Se identificó una sola figura correctamente. Hace falta más práctica."
        else:
            return "A ENTRENAR", "No se identificaron figuras correctamente. Es recomendable reforzar este ejercicio."

    def draw_intro():
        draw_openrehab_intro_screen(
            screen,
            width,
            height,
            test_name,
            patient_id,
            ["Identificá la figura con bajo contraste respecto al fondo."],
            start_text="ESPACIO para comenzar",
            back_text="ESC para volver al menú",
            badge_text="Percepción visual",
        )

    def draw_playing():
        bg = 205

        if difficulty == 1:
            outer_delta = -60
            inner_delta = -30
        elif difficulty == 2:
            outer_delta = -30
            inner_delta = -15
        else:
            outer_delta = -12
            inner_delta = -6

        screen.fill((bg, bg, bg))

        outer_color = tuple(max(0, min(255, bg + d)) for d in (outer_delta, outer_delta, outer_delta))
        inner_color = tuple(max(0, min(255, bg + d)) for d in (inner_delta, inner_delta, inner_delta))

        if target_shape == "rect":
            pygame.draw.rect(screen, outer_color, target_rect, border_radius=14)
        elif target_shape == "circle":
            pygame.draw.ellipse(screen, outer_color, target_rect)
        elif target_shape == "triangle":
            points = [
                (target_rect.centerx, target_rect.top),
                (target_rect.left, target_rect.bottom),
                (target_rect.right, target_rect.bottom)
            ]
            pygame.draw.polygon(screen, outer_color, points)

        inner_rect = target_rect.inflate(-8, -8)
        if target_shape == "rect":
            pygame.draw.rect(screen, inner_color, inner_rect, border_radius=14)
        elif target_shape == "circle":
            pygame.draw.ellipse(screen, inner_color, inner_rect)
        elif target_shape == "triangle":
            points = [
                (inner_rect.centerx, inner_rect.top),
                (inner_rect.left, inner_rect.bottom),
                (inner_rect.right, inner_rect.bottom)
            ]
            pygame.draw.polygon(screen, inner_color, points)

        elapsed = 0 if start_ticks is None else (pygame.time.get_ticks() - start_ticks) / 1000
        header = font.render(f"Ronda {current_round + 1}/{rounds}", True, (30, 30, 30))
        stats = font.render(f"Aciertos: {correct_count} | Errores: {incorrect_count} | Tiempo: {elapsed:0.1f}s", True, (30, 30, 30))
        screen.blit(header, (40, 26))
        screen.blit(stats, (40, 62))

        for button in buttons:
            pygame.draw.rect(screen, (80, 160, 255), button["rect"], border_radius=12)
            txt = font.render(button["label"], True, (255, 255, 255))
            txt_rect = txt.get_rect(center=button["rect"].center)
            screen.blit(txt, txt_rect)

    def draw_result():
        screen.fill((10, 37, 64))

        if not show_report:
            txt_surf = font_giant.render(final_metrics["rango"], True, (114, 211, 154))
            screen.blit(txt_surf, (width // 2 - txt_surf.get_width() // 2, 220))

            msg_surf = font_hud.render(final_metrics["msg"], True, (199, 217, 234))
            screen.blit(msg_surf, (width // 2 - msg_surf.get_width() // 2, 340))

            for rect, label, color in [
                (btn_reporte, "VER INFORME", (79, 195, 247)),
                (btn_volver, "VOLVER", (36, 72, 110))
            ]:
                pygame.draw.rect(screen, color, rect, border_radius=12)
                txt = font_button.render(label, True, (255, 255, 255))
                screen.blit(txt, txt.get_rect(center=rect.center))
        else:
            popup_rect = pygame.Rect(width // 2 - 300, 150, 600, 480)
            pygame.draw.rect(screen, (244, 248, 252), popup_rect, border_radius=20)
            pygame.draw.rect(screen, (43, 92, 136), popup_rect, 3, border_radius=20)

            title_surf = font_button.render("INFORME CLÍNICO DETALLADO", True, (10, 37, 64))
            screen.blit(title_surf, (width // 2 - title_surf.get_width() // 2, 180))

            info_lines = [
                f"Figuras correctas: {final_metrics['correctas']}/{final_metrics['total']}",
                f"Figuras incorrectas: {final_metrics['incorrectas']}",
                f"Tiempo total: {final_metrics['tiempo']}s",
                f"Tiempo promedio por figura: {final_metrics['tiempo_promedio']}s",
                f"Porcentaje de acierto: {final_metrics['porcentaje']}%"
            ]
            for i, line in enumerate(info_lines):
                line_surf = font_report.render(line, True, (36, 72, 110))
                screen.blit(line_surf, (width // 2 - 230, 250 + (i * 50)))

            pygame.draw.rect(screen, (180, 50, 50), btn_cerrar, border_radius=10)
            close_surf = font_button.render("CERRAR", True, (255, 255, 255))
            screen.blit(close_surf, close_surf.get_rect(center=btn_cerrar.center))

    running = True
    while running:
        mx, my = pygame.mouse.get_pos()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif state == "intro" and event.key == pygame.K_SPACE:
                    state = "playing"
                    show_report = False
                    current_round = 0
                    correct_count = 0
                    incorrect_count = 0
                    total_time = 0.0
                    avg_time = 0.0
                    start_ticks = pygame.time.get_ticks()
                    generate_round()
                elif state == "result" and event.key == pygame.K_RETURN and not show_report:
                    running = False

            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if state == "playing":
                    for button in buttons:
                        if button["rect"].collidepoint(mx, my):
                            is_correct = (
                                (button["label"] == "Rectángulo" and target_shape == "rect") or
                                (button["label"] == "Círculo" and target_shape == "circle") or
                                (button["label"] == "Triángulo" and target_shape == "triangle")
                            )

                            if is_correct:
                                correct_count += 1
                            else:
                                incorrect_count += 1

                            current_round += 1

                            if current_round >= rounds:
                                total_time = (pygame.time.get_ticks() - start_ticks) / 1000 if start_ticks else 0.0
                                avg_time = total_time / rounds if rounds else 0.0
                                porcentaje = round((correct_count / rounds) * 100) if rounds else 0
                                rango, msg = get_feedback(correct_count, rounds)
                                final_metrics = {
                                    "correctas": correct_count,
                                    "incorrectas": incorrect_count,
                                    "total": rounds,
                                    "tiempo": round(total_time, 2),
                                    "tiempo_promedio": round(avg_time, 2),
                                    "porcentaje": porcentaje,
                                    "rango": rango,
                                    "msg": msg
                                }
                                save_result_json(patient_id, test_key, final_metrics, attempts)
                                state = "result"
                            else:
                                generate_round()
                            break

                elif state == "result":
                    if btn_reporte.collidepoint(mx, my) and not show_report:
                        show_report = True
                    elif btn_volver.collidepoint(mx, my) and not show_report:
                        running = False
                    elif btn_cerrar.collidepoint(mx, my) and show_report:
                        show_report = False

        if state == "intro":
            draw_intro()
        elif state == "playing":
            draw_playing()
        elif state == "result":
            draw_result()

        pygame.display.flip()
        clock.tick(60)

    pygame.quit()



def run_acinetopsia_test(patient_id: str, test_key: str, test_name: str, difficulty: int):
    pygame.init()

    width, height = 1200, 750
    screen = pygame.display.set_mode((width, height))
    pygame.display.set_caption(f"{APP_TITLE} - {test_name}")

    clock = pygame.time.Clock()

    font = pygame.font.SysFont("arial", 24)
    font_hud = pygame.font.SysFont("arial", 26, bold=True)
    font_giant = pygame.font.SysFont("arial", 80, bold=True)
    font_button = pygame.font.SysFont("arial", 24, bold=True)
    font_report = pygame.font.SysFont("arial", 22)

    state = "intro"
    show_report = False
    attempts = 1

    total_targets = 8
    found_count = 0
    total_clicks = 0
    misclicks = 0
    duration_seconds = 25
    start_ticks = None
    total_time = 0.0
    avg_time = 0.0
    final_metrics = {}

    targets = []

    def create_targets():
        nonlocal targets
        targets = []
        for _ in range(total_targets):
            targets.append({
                "x": random.randint(50, 300),
                "y": random.randint(140, height - 70),
                "r": random.randint(20, 30),
                "speed": random.randint(3, 7),
                "active": True
            })

    create_targets()

    btn_reporte = pygame.Rect(width // 2 - 220, height - 130, 210, 55)
    btn_volver = pygame.Rect(width // 2 + 10, height - 130, 210, 55)
    btn_cerrar = pygame.Rect(width // 2 - 100, 560, 200, 45)

    def get_feedback(encontrados, total):
        if encontrados == total:
            return "EXCELENTE", "¡Excelente rendimiento! Marcaste correctamente todos los objetivos."
        elif encontrados == total - 1:
            return "MUY BIEN", "Muy buen trabajo. Solo faltó un objetivo."
        elif encontrados == total - 2:
            return "BIEN HECHO", "Buen desempeño. Lograste detectar la mayoría de los estímulos."
        elif encontrados == total - 3:
            return "SIGUE ASÍ", "Vas avanzando bien. Con más práctica podés mejorar aún más."
        elif encontrados == total - 4:
            return "A PRACTICAR", "Se encontraron varios objetivos, pero conviene seguir entrenando la percepción del movimiento."
        elif encontrados >= 1:
            return "A ENTRENAR", "Se detectaron pocos objetivos. Es recomendable reforzar este ejercicio."
        else:
            return "A ENTRENAR", "No se detectaron objetivos. Conviene repetir el ejercicio con acompañamiento."

    def finalize_result():
        nonlocal total_time, avg_time, final_metrics, state
        elapsed = (pygame.time.get_ticks() - start_ticks) / 1000 if start_ticks else 0.0
        total_time = min(elapsed, duration_seconds)
        avg_time = total_time / total_targets if total_targets else 0.0
        not_found = total_targets - found_count
        rango, msg = get_feedback(found_count, total_targets)
        porcentaje = round((found_count / total_targets) * 100) if total_targets else 0

        final_metrics = {
            "encontrados": found_count,
            "total": total_targets,
            "no_encontrados": not_found,
            "tiempo": round(total_time, 2),
            "tiempo_promedio": round(avg_time, 2),
            "clicks_totales": total_clicks,
            "misclicks": misclicks,
            "porcentaje": porcentaje,
            "rango": rango,
            "msg": msg
        }
        save_result_json(patient_id, test_key, final_metrics, attempts)
        state = "result"

    def draw_intro():
        draw_openrehab_intro_screen(
            screen,
            width,
            height,
            test_name,
            patient_id,
            ["Capturá con click los objetos que cruzan la pantalla antes de que termine el tiempo."],
            start_text="ESPACIO para comenzar",
            back_text="ESC para volver al menú",
            badge_text="Movimiento",
        )

    def draw_playing():
        bg = 240

        if difficulty == 1:
            delta = -140
        elif difficulty == 2:
            delta = -80
        else:
            delta = -40

        screen.fill((bg, bg, bg))

        elapsed = (pygame.time.get_ticks() - start_ticks) / 1000 if start_ticks else 0.0
        remaining = max(0, duration_seconds - elapsed)

        pygame.draw.rect(screen, (30, 30, 30), pygame.Rect(0, 0, width, 90))
        h1 = font.render(f"Capturados: {found_count}/{total_targets}", True, (255, 255, 255))
        h2 = font.render(f"Tiempo restante: {remaining:0.1f}s", True, (255, 230, 120))
        h3 = font.render(f"Clicks: {total_clicks} | Misclicks: {misclicks}", True, (255, 255, 255))
        screen.blit(h1, (20, 18))
        screen.blit(h2, (20, 52))
        screen.blit(h3, (820, 32))

        for target in targets:
            if target["active"]:
                circle_color = tuple(max(0, min(255, bg + delta)) for _ in range(3))
                border_delta = int(delta * 0.5)
                border_color = tuple(max(0, min(255, bg + border_delta)) for _ in range(3))

                pygame.draw.circle(screen, circle_color, (int(target["x"]), int(target["y"])), target["r"])
                pygame.draw.circle(screen, border_color, (int(target["x"]), int(target["y"])), target["r"], 2)

                # el borde tiene MENOS contraste que el relleno
                border_delta = int(delta * 0.5)
                border_color = tuple(max(0, min(255, bg + border_delta)) for _ in range(3))

                pygame.draw.circle(screen, circle_color, (int(target["x"]), int(target["y"])), target["r"])
                pygame.draw.circle(screen, border_color, (int(target["x"]), int(target["y"])), target["r"], 2)
    def draw_result():
        screen.fill((10, 37, 64))

        if not show_report:
            txt_surf = font_giant.render(final_metrics["rango"], True, (114, 211, 154))
            screen.blit(txt_surf, (width // 2 - txt_surf.get_width() // 2, 220))

            msg_surf = font_hud.render(final_metrics["msg"], True, (199, 217, 234))
            screen.blit(msg_surf, (width // 2 - msg_surf.get_width() // 2, 340))

            for rect, label, color in [
                (btn_reporte, "VER INFORME", (79, 195, 247)),
                (btn_volver, "VOLVER", (36, 72, 110))
            ]:
                pygame.draw.rect(screen, color, rect, border_radius=12)
                txt = font_button.render(label, True, (255, 255, 255))
                screen.blit(txt, txt.get_rect(center=rect.center))
        else:
            popup_rect = pygame.Rect(width // 2 - 300, 135, 600, 510)
            pygame.draw.rect(screen, (244, 248, 252), popup_rect, border_radius=20)
            pygame.draw.rect(screen, (43, 92, 136), popup_rect, 3, border_radius=20)

            title_surf = font_button.render("INFORME CLÍNICO DETALLADO", True, (10, 37, 64))
            screen.blit(title_surf, (width // 2 - title_surf.get_width() // 2, 165))

            info_lines = [
                f"Objetivos encontrados: {final_metrics['encontrados']}/{final_metrics['total']}",
                f"Objetivos no encontrados: {final_metrics['no_encontrados']}",
                f"Tiempo total: {final_metrics['tiempo']}s",
                f"Tiempo promedio por objetivo: {final_metrics['tiempo_promedio']}s",
                f"Clicks totales: {final_metrics['clicks_totales']}",
                f"Misclicks: {final_metrics['misclicks']}"
            ]
            for i, line in enumerate(info_lines):
                line_surf = font_report.render(line, True, (36, 72, 110))
                screen.blit(line_surf, (width // 2 - 235, 235 + (i * 45)))

            pygame.draw.rect(screen, (180, 50, 50), btn_cerrar, border_radius=10)
            close_surf = font_button.render("CERRAR", True, (255, 255, 255))
            screen.blit(close_surf, close_surf.get_rect(center=btn_cerrar.center))

    running = True

    while running:
        mx, my = pygame.mouse.get_pos()

        for event in pygame.event.get():

            if event.type == pygame.QUIT:
                running = False

            elif event.type == pygame.KEYDOWN:

                if event.key == pygame.K_ESCAPE:
                    running = False

                elif state == "intro" and event.key == pygame.K_SPACE:
                    state = "playing"
                    show_report = False
                    found_count = 0
                    total_clicks = 0
                    misclicks = 0
                    total_time = 0.0
                    avg_time = 0.0
                    final_metrics = {}
                    create_targets()
                    start_ticks = pygame.time.get_ticks()

                elif state == "result" and event.key == pygame.K_RETURN and not show_report:
                    running = False

            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:

                if state == "playing":
                    total_clicks += 1
                    clicked_target = False

                    for target in targets:
                        if not target["active"]:
                            continue

                        dx = mx - target["x"]
                        dy = my - target["y"]
                        inside = (dx * dx + dy * dy) <= (target["r"] * target["r"])

                        if inside:
                            target["active"] = False
                            found_count += 1
                            clicked_target = True

                            if found_count >= total_targets:
                                finalize_result()
                            break

                    if not clicked_target:
                        misclicks += 1

                elif state == "result":
                    if btn_reporte.collidepoint(mx, my) and not show_report:
                        show_report = True
                    elif btn_volver.collidepoint(mx, my) and not show_report:
                        running = False
                    elif btn_cerrar.collidepoint(mx, my) and show_report:
                        show_report = False

        if state == "playing":

            for target in targets:
                if target["active"]:
                    target["x"] += target["speed"]
                    if target["x"] > width + 30:
                        target["x"] = -30
                        target["y"] = random.randint(140, height - 70)

            elapsed = (pygame.time.get_ticks() - start_ticks) / 1000 if start_ticks else 0.0
            if elapsed >= duration_seconds and state == "playing":
                finalize_result()

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
        draw_openrehab_intro_screen(
            screen,
            width,
            height,
            test_name,
            patient_id,
            [
                "Llevá el cursor por el camino sin tocar los bordes.",
                "Usá las flechas para avanzar.",
            ],
            start_text="ESPACIO para comenzar",
            back_text="ESC para volver al menú",
            badge_text="Coordinación motora",
        )

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
        draw_openrehab_result_screen(
            screen,
            width,
            height,
            test_name,
            [f"Métrica principal: {final_metric} {final_unit}"],
            action_text="ENTER para volver",
            secondary_text="ESC para salir",
            title="Resultado guardado",
            badge_text="Resumen final",
        )

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
                save_result_json(patient_id, test_key, {final_unit: final_metric}, attempts)
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
        draw_openrehab_intro_screen(
            screen,
            width,
            height,
            test_name,
            patient_id,
            [
                "Tocá los objetivos lo más rápido y preciso posible.",
                "Van a cambiar de tamaño y posición.",
            ],
            start_text="ESPACIO para comenzar",
            back_text="ESC para volver al menú",
            badge_text="Precisión y velocidad",
        )

    def draw_playing():
        screen.fill((245, 245, 245))
        pygame.draw.rect(screen, (30, 30, 30), pygame.Rect(0, 0, width, 90))
        screen.blit(font.render(f"Intento {current_trial + 1}/{trials}", True, (255, 255, 255)), (20, 22))
        screen.blit(font.render(f"Aciertos: {hits}", True, (255, 230, 120)), (20, 55))

        pygame.draw.ellipse(screen, (72, 211, 154), target)
        pygame.draw.ellipse(screen, (20, 20, 20), target, 3)

    def draw_result():
        draw_openrehab_result_screen(
            screen,
            width,
            height,
            test_name,
            [f"Métrica principal: {final_metric} {final_unit}"],
            action_text="ENTER para volver",
            secondary_text="ESC para salir",
            title="Resultado guardado",
            badge_text="Resumen final",
        )

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
                    save_result_json(patient_id, test_key, {final_unit: final_metric}, attempts)
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
        draw_openrehab_intro_screen(
            screen,
            width,
            height,
            test_name,
            patient_id,
            [
                "El selector recorre opciones automáticamente.",
                "Presioná ESPACIO cuando esté sobre la opción objetivo.",
                f"Objetivo actual: {target_option}",
            ],
            start_text="ESPACIO para comenzar",
            back_text="ESC para volver al menú",
            badge_text="Scanning",
        )

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
        draw_openrehab_result_screen(
            screen,
            width,
            height,
            test_name,
            [f"Métrica principal: {final_metric} {final_unit}"],
            action_text="ENTER para volver",
            secondary_text="ESC para salir",
            title="Resultado guardado",
            badge_text="Resumen final",
        )

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
                        save_result_json(patient_id, test_key, {final_unit: final_metric}, attempts)
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
        draw_openrehab_intro_screen(
            screen,
            width,
            height,
            test_name,
            patient_id,
            ["Arrastrá el objeto hasta el área objetivo sin soltarlo."],
            start_text="ESPACIO para comenzar",
            back_text="ESC para volver al menú",
            badge_text="Drag & Drop",
        )

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
        draw_openrehab_result_screen(
            screen,
            width,
            height,
            test_name,
            [f"Métrica principal: {final_metric} {final_unit}"],
            action_text="ENTER para volver",
            secondary_text="ESC para salir",
            title="Resultado guardado",
            badge_text="Resumen final",
        )

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
                        save_result_json(patient_id, test_key, {final_unit: final_metric}, attempts)
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
        draw_openrehab_intro_screen(
            screen,
            width,
            height,
            test_name,
            patient_id,
            [
                "Mové el cursor adaptado hasta alcanzar los objetivos.",
                "La sensibilidad está aumentada para reducir el recorrido.",
                "Usá flechas y presioná ESPACIO para comenzar.",
            ],
            start_text="ESPACIO para comenzar",
            back_text="ESC para volver al menú",
            badge_text="Adaptación motora",
        )

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
        draw_openrehab_result_screen(
            screen,
            width,
            height,
            test_name,
            [f"Métrica principal: {final_metric} {final_unit}"],
            action_text="ENTER para volver",
            secondary_text="ESC para salir",
            title="Resultado guardado",
            badge_text="Resumen final",
        )

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
                    save_result_json(patient_id, test_key, {final_unit: final_metric}, attempts)
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
        draw_openrehab_intro_screen(
            screen,
            width,
            height,
            test_name,
            patient_id,
            [
                "Respondé a estímulos visuales y auditivos.",
                "Click para estímulo visual, B para estímulo auditivo.",
            ],
            start_text="ESPACIO para comenzar",
            back_text="ESC para volver al menú",
            badge_text="Reacción multimodal",
        )

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
        draw_openrehab_result_screen(
            screen,
            width,
            height,
            test_name,
            [f"Métrica principal: {final_metric} {final_unit}"],
            action_text="ENTER para volver",
            secondary_text="ESC para salir",
            title="Resultado guardado",
            badge_text="Resumen final",
        )

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
                        save_result_json(patient_id, test_key, {final_unit: final_metric}, attempts)
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
                        save_result_json(patient_id, test_key, {final_unit: final_metric}, attempts)
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
        draw_openrehab_intro_screen(
            screen,
            width,
            height,
            test_name,
            patient_id,
            ["Elegí el nombre correcto entre opciones parecidas."],
            start_text="ESPACIO para comenzar",
            back_text="ESC para volver al menú",
            badge_text="Lenguaje",
        )

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
        draw_openrehab_result_screen(
            screen,
            width,
            height,
            test_name,
            [f"Métrica principal: {final_metric} {final_unit}"],
            action_text="ENTER para volver",
            secondary_text="ESC para salir",
            title="Resultado guardado",
            badge_text="Resumen final",
        )

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
                            save_result_json(patient_id, test_key, {final_unit: final_metric}, attempts)
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
        draw_openrehab_intro_screen(
            screen,
            width,
            height,
            test_name,
            patient_id,
            [f"Presioná ESPACIO si la figura actual coincide con la de hace {n_value} pasos."],
            start_text="ENTER para comenzar",
            back_text="ESC para volver al menú",
            badge_text="Memoria de trabajo",
        )

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
        draw_openrehab_result_screen(
            screen,
            width,
            height,
            test_name,
            [
                f"Métrica principal: {final_metric} {final_unit}",
                f"Coincidencias reales en la secuencia: {total_matches}",
            ],
            action_text="ENTER para volver",
            secondary_text="ESC para salir",
            title="Resultado guardado",
            badge_text="Resumen final",
        )

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
                        save_result_json(patient_id, test_key, {final_unit: final_metric}, attempts)
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
        draw_openrehab_intro_screen(
            screen,
            width,
            height,
            test_name,
            patient_id,
            ["Elegí el color de la tinta, ignorando la palabra escrita."],
            start_text="ESPACIO para comenzar",
            back_text="ESC para volver al menú",
            badge_text="Inhibición",
        )

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
        draw_openrehab_result_screen(
            screen,
            width,
            height,
            test_name,
            [f"Métrica principal: {final_metric} {final_unit}"],
            action_text="ENTER para volver",
            secondary_text="ESC para salir",
            title="Resultado guardado",
            badge_text="Resumen final",
        )

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
                            save_result_json(patient_id, test_key, {final_unit: final_metric}, attempts)
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
        draw_openrehab_intro_screen(
            screen,
            width,
            height,
            test_name,
            patient_id,
            ["Elegí la palabra que completa correctamente la oración."],
            start_text="ESPACIO para comenzar",
            back_text="ESC para volver al menú",
            badge_text="Comprensión semántica",
        )

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
        draw_openrehab_result_screen(
            screen,
            width,
            height,
            test_name,
            [f"Métrica principal: {final_metric} {final_unit}"],
            action_text="ENTER para volver",
            secondary_text="ESC para salir",
            title="Resultado guardado",
            badge_text="Resumen final",
        )

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
                            save_result_json(patient_id, test_key, {final_unit: final_metric}, attempts)
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
        draw_openrehab_intro_screen(
            screen,
            width,
            height,
            test_name,
            patient_id,
            ["Elegí el elemento que no pertenece al grupo."],
            start_text="ESPACIO para comenzar",
            back_text="ESC para volver al menú",
            badge_text="Razonamiento lógico",
        )

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
        draw_openrehab_result_screen(
            screen,
            width,
            height,
            test_name,
            [f"Métrica principal: {final_metric} {final_unit}"],
            action_text="ENTER para volver",
            secondary_text="ESC para salir",
            title="Resultado guardado",
            badge_text="Resumen final",
        )

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
                            save_result_json(patient_id, test_key, {final_unit: final_metric}, attempts)
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
        draw_openrehab_intro_screen(
            screen,
            width,
            height,
            test_name,
            patient_id,
            ["Seleccioná los pasos en el orden correcto de la actividad."],
            start_text="ESPACIO para comenzar",
            back_text="ESC para volver al menú",
            badge_text="Secuenciación",
        )

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
        draw_openrehab_result_screen(
            screen,
            width,
            height,
            test_name,
            [f"Métrica principal: {final_metric} {final_unit}"],
            action_text="ENTER para volver",
            secondary_text="ESC para salir",
            title="Resultado guardado",
            badge_text="Resumen final",
        )

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
                                save_result_json(patient_id, test_key, {final_unit: final_metric}, attempts)
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


    def get_tests_dict_for_current_area(self):
        if self.current_area_key.get() == "area1":
            return AREA_1_TESTS
        if self.current_area_key.get() == "area2":
            return AREA_2_TESTS
        return AREA_3_TESTS

    def open_saved_report(self, result: dict):
        colors = {
            "bg_main": "#0A2540",
            "bg_card": "#F4F8FC",
            "border": "#2B5C88",
            "title": "#0A2540",
            "text": "#24435F",
            "accent": "#4FC3F7",
            "danger": "#B43232",
        }

        test_dict = {}
        test_dict.update(AREA_1_TESTS)
        test_dict.update(AREA_2_TESTS)
        test_dict.update(AREA_3_TESTS)

        top = tk.Toplevel(self.root)
        top.title("Informe guardado")
        top.geometry("760x620")
        top.configure(bg=colors["bg_main"])
        top.transient(self.root)
        top.grab_set()

        card = tk.Frame(top, bg=colors["bg_card"], highlightthickness=2, highlightbackground=colors["border"])
        card.pack(fill="both", expand=True, padx=28, pady=28)

        tk.Frame(card, bg=colors["accent"], height=8).pack(fill="x", side="top")

        pretty_test = test_dict.get(result.get("test", ""), result.get("test", "Test"))
        tk.Label(
            card,
            text="INFORME CLÍNICO DETALLADO",
            font=("Arial", 18, "bold"),
            fg=colors["title"],
            bg=colors["bg_card"]
        ).pack(pady=(20, 6))

        tk.Label(
            card,
            text=pretty_test,
            font=("Arial", 13, "bold"),
            fg=colors["text"],
            bg=colors["bg_card"]
        ).pack()

        container = tk.Frame(card, bg=colors["bg_card"])
        container.pack(fill="both", expand=True, padx=26, pady=(18, 16))

        scrollbar = tk.Scrollbar(container)
        scrollbar.pack(side="right", fill="y")

        text = tk.Text(
            container,
            yscrollcommand=scrollbar.set,
            bg=colors["bg_card"],
            fg=colors["text"],
            font=("Arial", 12),
            wrap="word",
            relief="flat",
            bd=0,
            padx=6,
            pady=6,
            spacing1=3,
            spacing3=8
        )
        text.pack(side="left", fill="both", expand=True)
        scrollbar.config(command=text.yview)

        for line in build_report_lines(result):
            text.insert("end", line + "\n")

        text.config(state="disabled")

        tk.Button(
            card,
            text="CERRAR",
            font=("Arial", 12, "bold"),
            bg=colors["danger"],
            fg="white",
            activebackground="#982929",
            activeforeground="white",
            relief="flat",
            bd=0,
            cursor="hand2",
            command=top.destroy
        ).pack(pady=(0, 20), ipadx=18, ipady=8)

    def populate_history_panel(self, parent, patient_id: str, tests_dict: dict):
        for child in parent.winfo_children():
            child.destroy()

        history_results = load_patient_results(patient_id)

        if not history_results:
            tk.Label(
                parent,
                text="No se encontraron resultados previos para este paciente en la carpeta /results.",
                font=("Arial", 11),
                fg="#C7D9EA",
                bg="#102F4E",
                justify="left",
                wraplength=420
            ).pack(anchor="w", padx=14, pady=14)
            return

        canvas = tk.Canvas(parent, bg="#102F4E", highlightthickness=0, bd=0)
        scrollbar = tk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        inner = tk.Frame(canvas, bg="#102F4E")

        inner.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        for item in history_results:
            pretty_test = tests_dict.get(item.get("test", ""), item.get("test", "Test desconocido"))
            summary = get_metric_summary(item)

            card = tk.Frame(
                inner,
                bg="#163A63",
                highlightthickness=1,
                highlightbackground="#2B5C88"
            )
            card.pack(fill="x", padx=10, pady=8)

            tk.Label(
                card,
                text=pretty_test,
                font=("Arial", 11, "bold"),
                fg="#F4F8FC",
                bg="#163A63",
                anchor="w",
                justify="left",
                wraplength=320
            ).pack(anchor="w", padx=12, pady=(10, 2))

            tk.Label(
                card,
                text=f"{item.get('fecha', '-')}",
                font=("Arial", 10),
                fg="#C7D9EA",
                bg="#163A63",
                anchor="w"
            ).pack(anchor="w", padx=12)

            tk.Label(
                card,
                text=summary,
                font=("Arial", 10),
                fg="#8FB1CC",
                bg="#163A63",
                anchor="w",
                justify="left",
                wraplength=320
            ).pack(anchor="w", padx=12, pady=(4, 10))

            tk.Button(
                card,
                text="Ver informe",
                font=("Arial", 10, "bold"),
                bg="#4FC3F7",
                fg="white",
                activebackground="#35B5EC",
                activeforeground="white",
                relief="flat",
                bd=0,
                cursor="hand2",
                command=lambda result=item: self.open_saved_report(result)
            ).pack(anchor="e", padx=12, pady=(0, 12), ipadx=10, ipady=4)

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
            bg="#4DA6FF",              # ← azul celeste
            fg="white",
            activebackground="#3A8EDB",  # ← azul más oscuro al click
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
            bg="#FFD6A5",
            fg="white",
            activebackground="#FFCC8F",
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
            bg="#F6E7A1",
            fg="white",
            activebackground="#EEDB84",
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
                summary = get_metric_summary(last_result)
                date = last_result.get("fecha", "-")
                attempts = last_result.get("intentos", "-")

                comparison_text.config(
                    text=(
                        f"Último resultado encontrado:\n\n"
                        f"• Fecha: {date}\n"
                        f"• Resumen: {summary}\n"
                        f"• Intentos: {attempts}\n\n"
                        f"Podés revisar el detalle completo desde el historial del paciente."
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


        history_container = tk.Frame(
            right_panel,
            bg="#102F4E",
            highlightthickness=1,
            highlightbackground=border_card
        )
        history_container.pack(fill="both", expand=True, padx=20, pady=(0, 20))

        self.populate_history_panel(history_container, patient_id, self.get_tests_dict_for_current_area())


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
                summary = get_metric_summary(last_result)
                date = last_result.get("fecha", "-")
                attempts = last_result.get("intentos", "-")

                comparison_text.config(
                    text=(
                        f"Último resultado encontrado:\n\n"
                        f"• Fecha: {date}\n"
                        f"• Resumen: {summary}\n"
                        f"• Intentos: {attempts}\n\n"
                        f"Podés revisar el detalle completo desde el historial del paciente."
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


        history_container = tk.Frame(
            right_panel,
            bg="#102F4E",
            highlightthickness=1,
            highlightbackground=border_card
        )
        history_container.pack(fill="both", expand=True, padx=20, pady=(0, 20))

        self.populate_history_panel(history_container, patient_id, self.get_tests_dict_for_current_area())


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
                summary = get_metric_summary(last_result)
                date = last_result.get("fecha", "-")
                attempts = last_result.get("intentos", "-")

                comparison_text.config(
                    text=(
                        f"Último resultado encontrado:\n\n"
                        f"• Fecha: {date}\n"
                        f"• Resumen: {summary}\n"
                        f"• Intentos: {attempts}\n\n"
                        f"Podés revisar el detalle completo desde el historial del paciente."
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


        history_container = tk.Frame(
            right_panel,
            bg="#102F4E",
            highlightthickness=1,
            highlightbackground=border_card
        )
        history_container.pack(fill="both", expand=True, padx=20, pady=(0, 20))

        self.populate_history_panel(history_container, patient_id, self.get_tests_dict_for_current_area())


        bottom_wrap = tk.Frame(outer, bg=bg_main)
        bottom_wrap.pack(fill="x", side="bottom")

        wave_2 = tk.Frame(bottom_wrap, bg=accent_green, height=4)
        wave_2.pack(fill="x", side="bottom")

        wave_1 = tk.Frame(bottom_wrap, bg=accent_blue, height=10)
        wave_1.pack(fill="x", side="bottom")


    # --------------------------------------------------------
    # SELECCIÓN DE DIFICULTAD
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
        
        # En lugar de ejecutar, vamos a la nueva pantalla
        self.build_difficulty_selector(patient_id, test_key, test_name)
        
        
    def build_difficulty_selector(self, patient_id: str, test_key: str, test_name: str):
        self.clear_main()
        
        bg_main = "#0A2540"
        bg_card = "#163A63"
        text_primary = "#F4F8FC"
        btn_secondary = "#243B53"

        outer = tk.Frame(self.main_container, bg=bg_main)
        outer.pack(fill="both", expand=True)

        header = tk.Frame(outer, bg=bg_main)
        header.pack(pady=(50, 20))

        tk.Label(
            header, 
            text="Configuración del Test", 
            font=("Arial", 24, "bold"), 
            fg=text_primary, bg=bg_main
        ).pack()
        
        tk.Label(
            header, 
            text=f"Actividad: {test_name}", 
            font=("Arial", 14), 
            fg="#C7D9EA", bg=bg_main
        ).pack(pady=10)

        card = tk.Frame(outer, bg=bg_card, highlightthickness=1, highlightbackground="#2B5C88")
        card.pack(pady=20, padx=50, ipadx=40, ipady=40)

        tk.Label(
            card, 
            text="Seleccioná el nivel de dificultad", 
            font=("Arial", 16, "bold"), 
            fg="white", bg=bg_card
        ).pack(pady=(0, 30))

        # Estilo de botones de dificultad
        diff_settings = [
            ("Fácil", "#72D39A", 1),      # Texto, Color, Valor numérico
            ("Medio", "#FBC02D", 2),
            ("Difícil", "#F44336", 3)
        ]

        for text, color, val in diff_settings:
            tk.Button(
                card,
                text=text,
                font=("Arial", 14, "bold"),
                bg=color,
                fg="white",
                width=20,
                cursor="hand2",
                relief="flat",
                # Aquí llamamos a la ejecución real del juego
                command=lambda v=val: self.execute_pygame_with_difficulty(patient_id, test_key, test_name, v)
            ).pack(pady=10, ipady=5)

        tk.Button(
            outer,
            text="Cancelar y volver",
            font=("Arial", 12),
            bg=btn_secondary,
            fg="white",
            relief="flat",
            command=lambda: self.build_area_selector(patient_id)
        ).pack(pady=20)   

    def execute_pygame_with_difficulty(self, patient_id, test_key, test_name, difficulty):
        """
        Lanza el juego de Pygame cerrando temporalmente la ventana de Tkinter.
        Pasa el parámetro 'difficulty' a los juegos que ya están actualizados.
        """
        # Ocultamos la ventana principal de Tkinter
        self.root.withdraw()
        
        try:
            # --- ÁREA 1: VISIÓN Y PERCEPCIÓN ---
            if test_key == "exploracion_faro":
                # Juego actualizado con rangos aleatorios y dificultad
                run_exploracion_faro_test(patient_id, test_key, test_name, difficulty)

            elif test_key == "anclaje_visual":
                # Juego actualizado con parpadeo y ancho variable
                run_anclaje_visual_test(patient_id, test_key, test_name, difficulty)

            elif test_key == "complejidad_gradual":
                run_complejidad_gradual_test(patient_id, test_key, test_name, difficulty)

            elif test_key == "cancelacion_estimulos":
                run_cancelacion_estimulos_test(patient_id, test_key, test_name, difficulty)

            elif test_key == "figura_fondo":
                run_figura_fondo_test(patient_id, test_key, test_name, difficulty)

            elif test_key == "acinetopsia":
                run_acinetopsia_test(patient_id, test_key, test_name, difficulty)

            # --- ÁREA 2: CONTROL MOTOR Y ACCESO ---
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

            # --- ÁREA 3: COGNICIÓN Y LENGUAJE ---
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
                # Caso por defecto si el test no tiene una función específica
                run_pygame_test(patient_id, test_key, test_name)

        finally:
            # Volvemos a mostrar la ventana de Tkinter al cerrar Pygame
            self.root.deiconify()
            
            # Recargamos el menú del área correspondiente para ver los nuevos resultados
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