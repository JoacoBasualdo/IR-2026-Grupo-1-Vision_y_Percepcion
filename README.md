# 🧠 OpenRehab ACV – Plataforma de Evaluación y Rehabilitación

Plataforma interactiva desarrollada en Python para la evaluación y rehabilitación de pacientes con Accidente Cerebrovascular (ACV).

---

## 📌 Descripción

OpenRehab ACV es un sistema modular que permite ejecutar múltiples tests terapéuticos orientados a:

- 🟦 Visión y percepción  
- 🟩 Control motor y acceso  
- 🟨 Cognición y lenguaje  

Actualmente, el desarrollo se encuentra **plenamente funcional en el área de Visión y Percepción**, mientras que las demás áreas se encuentran en una **versión alfa**, con bases implementadas y potencial de expansión futura.

El sistema combina interfaces gráficas en **Tkinter** con actividades interactivas en **Pygame**, permitiendo evaluar el desempeño del paciente y registrar métricas objetivas.

---

## 👥 Población objetivo

La aplicación está dirigida principalmente a pacientes que han sufrido un **Accidente Cerebrovascular (ACV)** y presentan alteraciones en:

- Percepción visual  
- Atención  
- Coordinación viso-motora  
- Procesamiento cognitivo  

También puede ser utilizada por:

- Profesionales de la salud (kinesiólogos, terapeutas ocupacionales, fonoaudiólogos)  
- Centros de rehabilitación neurológica  
- Pacientes en etapas de rehabilitación domiciliaria  

El sistema está diseñado para adaptarse a distintos niveles de severidad, permitiendo su uso tanto en etapas tempranas como avanzadas del proceso de recuperación.

---

## 🎯 Objetivo

Desarrollar una herramienta accesible que permita:

- Evaluar funciones perceptuales, cognitivas y motoras  
- Obtener métricas cuantitativas del desempeño  
- Registrar evolución del paciente mediante archivos JSON  
- Facilitar el seguimiento clínico  

---

## 🧩 Estado del desarrollo

| Área                     | Estado                  |
|--------------------------|------------------------|
| 🟦 Visión y Percepción   | ✅ Completo y funcional |
| 🟩 Control Motor         | ⚠️ Versión alfa        |
| 🟨 Cognición y Lenguaje  | ⚠️ Versión alfa        |

---

## 🧪 Área 1 – Visión y Percepción

### 🔹 Exploración de Faro (Neglect)
Evalúa la exploración visual y posibles omisiones en hemicampos.

### 🔹 Anclaje Visual
Entrena fijación visual y control atencional frente a distractores.

### 🔹 Complejidad Gradual
Aumenta la carga visual progresivamente para evaluar procesamiento.

### 🔹 Cancelación de Estímulos
Evaluación de precisión, omisiones y tiempos de respuesta.

### 🔹 Figura-Fondo
Discriminación de estímulos relevantes en entornos complejos.

### 🔹 Acinetopsia (Movimiento)
Evaluación de percepción de estímulos en movimiento.

---

## 🟩 Área 2 – Control Motor

Módulos en desarrollo orientados a coordinación y control fino.

---

## 🟨 Área 3 – Cognición y Lenguaje

Estructuras iniciales para evaluación cognitiva.

---

## 🛠️ Tecnologías utilizadas

- Python 3  
- Tkinter  
- Pygame  
- SpeechRecognition  
- JSON  

---

## ⚙️ Instalación

### 🔹 Requisitos previos

- Python 3.8 o superior  
- Micrófono (opcional, para funciones de voz)  

---

## 🔹 Clonar el repositorio

```bash
git clone https://github.com/tu-repo/openrehab.git
cd openrehab
```

## 🔹Descargar las dependencias

```bash
pip install -r requirements.txt
```
