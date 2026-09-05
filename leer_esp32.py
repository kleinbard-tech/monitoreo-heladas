import os
import threading
import time
from datetime import datetime
from flask import Flask, jsonify, send_from_directory

# Se intenta importar pyserial sin romper la app en servidores sin puerto COM
try:
    import serial
except ImportError:
    serial = None


# =====================================================
# CONFIGURACIÓN
# =====================================================

PUERTO = "COM3"
BAUDRATE = 115200


# =====================================================
# FLASK
# =====================================================

app = Flask(__name__)


# =====================================================
# VARIABLES DE DATOS
# =====================================================

datos_actuales = {}
historial = []


# =====================================================
# LECTURA DEL ESP32 (PUERTO SERIE)
# =====================================================

def leer_esp32():
    global datos_actuales
    global historial

    if serial is None:
        print("⚠ Librería 'pyserial' no disponible o entorno sin puerto COM.")
        return

    while True:
        try:
            print("Intentando conectar con", PUERTO)

            esp32 = serial.Serial(
                PUERTO,
                BAUDRATE,
                timeout=1
            )

            print("ESP32 conectado en:", PUERTO)
            print("Esperando datos...\n")

            while True:
                linea = (
                    esp32.readline()
                    .decode("utf-8", errors="ignore")
                    .strip()
                )

                if not linea:
                    continue

                # BUSCAR PAQUETE DE DATOS
                if linea.startswith("DATOS:"):
                    datos = linea.replace("DATOS:", "").strip()
                    valores = datos.split(",")

                    if len(valores) == 7:
                        try:
                            nodo = int(valores[0])
                            medicion = int(valores[1])
                            temperatura_ds = float(valores[2])
                            temperatura_dht = float(valores[3])
                            humedad = float(valores[4])
                            punto_rocio = float(valores[5])
                            estado = valores[6]

                            fecha_hora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                            registro = {
                                "fechaHora": fecha_hora,
                                "nodo": nodo,
                                "medicion": medicion,
                                "temperaturaDS": temperatura_ds,
                                "temperaturaDHT": temperatura_dht,
                                "humedad": humedad,
                                "puntoRocio": punto_rocio,
                                "estado": estado
                            }

                            datos_actuales[nodo] = registro
                            historial.append(registro)

                            print(
                                "Nodo:", nodo,
                                "| Medición:", medicion,
                                "| T:", temperatura_ds, "°C",
                                "| HR:", humedad, "%",
                                "| Td:", punto_rocio, "°C"
                            )

                        except ValueError:
                            print("Error al interpretar los datos recibidos.")

        except Exception as e:
            print(f"\n⚠ No se pudo conectar al puerto {PUERTO}: {e}")
            print("Esperando reconexión en 5 segundos...\n")
            time.sleep(5)


# =====================================================
# RUTAS DE LA PÁGINA WEB Y ARCHIVOS ESTÁTICOS
# =====================================================

@app.route("/")
def pagina_principal():
    return send_from_directory(".", "index.html")


@app.route("/estilo.css")
def estilo():
    return send_from_directory(".", "estilo.css")


@app.route("/script.js")
def javascript():
    return send_from_directory(".", "script.js")


@app.route("/logo-unco.jpg")
def logo_unco():
    return send_from_directory(".", "logo-unco.jpg")


# =====================================================
# RUTAS DE LA API (DATOS E HISTORIAL)
# =====================================================

@app.route("/datos", methods=["GET"])
def obtener_datos():
    return jsonify(datos_actuales)


@app.route("/historial", methods=["GET"])
def obtener_historial():
    return jsonify(historial)


# Ruta opcional para recibir datos por HTTP POST directamente desde los ESP32 vía Wi-Fi
@app.route("/api/medicion", methods=["POST"])
def recibir_medicion():
    from flask import request
    try:
        data = request.get_json()
        nodo = int(data.get("nodo"))
        
        data["fechaHora"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        datos_actuales[nodo] = data
        historial.append(data)
        
        return jsonify({"status": "ok", "message": "Datos recibidos correctamente"}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400


# =====================================================
# INICIO DEL SERVIDOR
# =====================================================

if __name__ == "__main__":

    # Iniciar el hilo de lectura del puerto serie en segundo plano
    hilo = threading.Thread(target=leer_esp32, daemon=True)
    hilo.start()

    # Tomar el puerto asignado por Render o usar el 5000 por defecto en local
    port = int(os.environ.get("PORT", 5000))

    print("\n========================================")
    print("      SERVIDOR WEB - MONITOREO")
    print("========================================\n")
    print(f"Servidor iniciado en el puerto: {port}")
    print("========================================\n")

    app.run(
        host="0.0.0.0",
        port=port
    )