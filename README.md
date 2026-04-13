\# 🎯 FocusE - IA Contextual sin perder el foco



> \*\*Analiza cualquier cosa en tu pantalla con un solo atajo de teclado.\*\* > Una herramienta ligera para desarrolladores y usuarios avanzados que integra la potencia de Gemini Vision directamente en tu flujo de trabajo.



FocusE elimina la fricción de tener que copiar, guardar y subir imágenes a una IA. Con un simple atajo, capturas lo que estás viendo y empiezas a chatear con Gemini al instante.



\---



\## 🚀 Descarga rápida (Windows)



Si no quieres líos de código, descarga la versión lista para usar:



1\. Ve a la sección de \*\*\[Releases](https://github.com/majony78/FocusE/releases)\*\*.

2\. Descarga el archivo `FocusE\_Windows.zip`.

3\. Descomprime y ejecuta el `.exe`.

4\. \*\*Configuración:\*\* La primera vez te pedirá tu API Key de Gemini (puedes conseguir una gratis en Google AI Studio). Se guarda localmente y es 100% privada.

5\. Estamos usando una de la versiones más baratas y funcionales  que es: "gemini-3.1-flash-lite-preview".



\---



\## ⚡ Atajos de teclado



\* `CTRL + ALT + S`: \*\*Captura y Pregunta.\*\* Toma una captura de tu pantalla actual y abre el chat de IA.

\* `CTRL + ALT + Q`: \*\*Cerrar programa.\*\* Cierra FocusE por completo.



\---



\## 💻 Para Desarrolladores (Open Source)



Si quieres ver el código o modificarlo:



\### Tecnologías usadas:

\* \*\*Lenguaje:\*\* Python 3.

\* \*\*Backend:\*\* Flask \& Flask-SocketIO.

\* \*\*IA:\*\* Google Generative AI (Gemini Flash 1.5).

\* \*\*UI:\*\* HTML5/JS (Custom Chrome Interface) + CustomTkinter.



\### Instalación:

1\. Clona el repo: `git clone https://github.com/majony78/FocusE.git`

2\. Instala dependencias: `pip install Flask Flask-SocketIO Pillow google-generativeai keyboard customtkinter`

3\. Ejecuta como administrador: `python main.py`



\---



\## 🔒 Privacidad

FocusE no almacena tus imágenes en la nube. Todo el historial y las capturas se gestionan en una base de datos local SQLite (`focus\_e.db`) en tu propio ordenador.

