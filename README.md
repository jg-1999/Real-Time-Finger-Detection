# Real-Time Finger Detection

Aplicacion Python con OpenCV y MediaPipe para contar en vivo cuantos dedos hay levantados en una o dos manos.

## Instalacion

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Si aparece un error relacionado con `mediapipe.solutions`, reinstala MediaPipe en el entorno activo:

```powershell
pip uninstall -y mediapipe
pip install -r requirements.txt
```

El proyecto fija `mediapipe==0.10.21` porque conserva la API clasica `solutions` usada por esta app.

## Ejecucion

```powershell
python main.py
```

Opciones utiles:

```powershell
python main.py --camera 0 --hands 2 --width 1280 --height 720
python main.py --hands 1
python main.py --dominant-hand Right
python main.py --thumb-mode flip
```

## Controles

- `Q` o `ESC`: salir.
- `R`: reiniciar la estabilidad del conteo.
- `H`: invertir la regla del pulgar si tu camara lo detecta al reves.

## Notas

La deteccion funciona mejor con la palma visible, buena luz y la mano completa dentro del encuadre. El conteo usa una ventana temporal corta para reducir parpadeos entre frames.
