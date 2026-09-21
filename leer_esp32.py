import csv
import json
import os
import threading
import time
from datetime import datetime
from flask import Flask, jsonify, send_from_directory

# Librerías opcionales según el entorno (Local o Render)
try:
    import serial
except ImportError:
    serial = None

try:
    import requests
except ImportError:
    requests = None

try:
    import paho.mqtt.client as mqtt
except ImportError:
    mqtt = None


# =====================================================
# CONFIGURACIONES
# =====================================================
PUERTO_SERIE = "COM3"
BAUDRATE = 115200
URL_RENDER = "https://monitoreo-heladas.onrender.com/api/medicion"

# Configuración HiveMQ Cloud (MQTT para Dragino OLG02)
MQTT_HOST = "45601dd6ca2f47d3aacd8eef0079c27e.s1.eu.hivemq.cloud"
MQTT_PORT = 8883
MQTT_USER = "matias_heladas"
MQTT_PASS = "Monitoreoheladas"
MQTT_TOPIC_UPLINK = "monitoreo-heladas/uplink"


# =====================================================
# FLASK & MEMORIA EN TIEMPO REAL
# =====================================================
app = Flask(__name__)

datos_actuales = {}
historial = []


# =====================================================
# LÓGICA DE NEGOCIO: DETERMINAR ESTADO EN PYTHON
# =====================================================
def determinar_estado(temperatura_ds, punto_rocio):
    """Calcula el estado de alerta en base a la temperatura de la sonda y el punto de rocío."""
    if temperatura_ds <= 0.0:
        return "HELADA"

    diferencia = temperatura_ds - punto_rocio

    if temperatura_ds <= 3.0 and diferencia <= 2.0:
        return "RIESGO"

    return "NORMAL"


# =====================================================
# GUARDAR EN CSV MENSUAL
# =====================================================
def guardar_en_csv(registro):
    try:
        if not os.path.exists("registros"):
            os.makedirs("registros")

        solo_fecha = registro["fechaHora"].split(" ")[0]
        anio_mes = solo_fecha[:7]

        nombre_archivo = f"registros/historial_{anio_mes}.csv"
        archivo_existe = os.path.exists(nombre_archivo)

        with open(nombre_archivo, mode="a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            if not archivo_existe:
                writer.writerow([
                    "FechaHora",
                    "Nodo",
                    "Medicion",
                    "TemperaturaDS",
                    "TemperaturaDHT",
                    "Humedad",
                    "PuntoRocio",
                    "Estado",
                ])

            writer.writerow([
                registro.get("fechaHora", ""),
                registro.get("nodo", 1),
                registro.get("medicion", 0),
                registro.get("temperaturaDS", 0.0),
                registro.get("temperaturaDHT", 0.0),
                registro.get("humedad", 0.0),
                registro.get("puntoRocio", 0.0),
                registro.get("estado", "NORMAL"),
            ])
    except Exception as e:
        print(f"⚠ Error al guardar en CSV: {e}")


# =====================================================
# PARSER UNIFICADO DE TRAMAS ("DATOS:1,1,14.2,14.5,65.0,7.8")
# =====================================================
def procesar_cadena_datos(cadena_texto):
    """Recibe la trama limpia sin el prefijo DATOS: y la convierte en diccionario."""
    try:
        valores = cadena_texto.replace("DATOS:", "").strip().split(",")

        # AHORA ESPERAMOS 6 VALORES (sin el estado)
        if len(valores) == 6:
            nodo = int(valores[0])
            medicion = int(valores[1])
            temp_ds = float(valores[2])
            temp_dht = float(valores[3])
            humedad = float(valores[4])
            punto_rocio = float(valores[5])

            # Determinamos el estado usando TU función de Python
            estado = determinar_estado(temp_ds, punto_rocio)
            fecha_hora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            return {
                "fechaHora": fecha_hora,
                "nodo": nodo,
                "medicion": medicion,
                "temperaturaDS": temp_ds,
                "temperaturaDHT": temp_dht,
                "humedad": humedad,
                "puntoRocio": punto_rocio,
                "estado": estado,
                "conectado": True,
            }
        else:
            print(f"⚠ Cantidad de parámetros incorrecta ({len(valores)} de 6 esperados)")
    except Exception as e:
        print(f"⚠ Error parseando trama: {e}")

    return None


# =====================================================
# 1. ESCUCHA VÍA MQTT (HIVERMQ CLOUD / DRAGINO)
# =====================================================
def on_connect(client, userdata, flags, rc, properties=None):
    if rc == 0:
        print(" Connected to HiveMQ Cloud Broker!")
        client.subscribe(MQTT_TOPIC_UPLINK, qos=1)
    else:
        print(f"⚠ Error de conexión MQTT: {rc}")


def on_message(client, userdata, msg):
    try:
        payload = msg.payload.decode("utf-8")
        print(f"\n Mensaje MQTT recibido: {payload}")

        registro = procesar_cadena_datos(payload)
        if registro:
            nodo = registro["nodo"]
            datos_actuales[nodo] = registro
            historial.append(registro)
            guardar_en_csv(registro)

            print(
                f" MQTT -> Nodo: {nodo} | TempDS: {registro['temperaturaDS']}°C | "
                f"P.Rocío: {registro['puntoRocio']}°C | Estado: {registro['estado']}"
            )
    except Exception as e:
        print(f"⚠ Error procesando MQTT: {e}")


def iniciar_mqtt():
    if mqtt is None:
        print("⚠ 'paho-mqtt' no instalado. Hilo MQTT deshabilitado.")
        return

    while True:
        try:
            try:
                client = mqtt.Client(client_id="Servidor_Flask_Render", protocol=mqtt.MQTTv5)
            except AttributeError:
                client = mqtt.Client(client_id="Servidor_Flask_Render")

            client.username_pw_set(MQTT_USER, MQTT_PASS)
            client.tls_set()
            client.on_connect = on_connect
            client.on_message = on_message

            client.connect(MQTT_HOST, MQTT_PORT, keepalive=60)
            client.loop_forever()
        except Exception as e:
            print(f"⚠ Reintentando conexión MQTT en 5s... ({e})")
            time.sleep(5)


# =====================================================
# 2. ESCUCHA VÍA PUERTO SERIE (RESPALDO LOCAL)
# =====================================================
def leer_esp32_serie():
    global datos_actuales, historial

    if serial is None:
        print("⚠ 'pyserial' no instalado. Lectura Serie deshabilitada.")
        return

    while True:
        try:
            esp32 = serial.Serial(PUERTO_SERIE, BAUDRATE, timeout=1)
            print(f"ESP32 conectado en Serie: {PUERTO_SERIE}")

            while True:
                linea = esp32.readline().decode("utf-8", errors="ignore").strip()

                if linea.startswith("DATOS:"):
                    registro = procesar_cadena_datos(linea)

                    if registro:
                        nodo = registro["nodo"]
                        datos_actuales[nodo] = registro
                        historial.append(registro)
                        guardar_en_csv(registro)

                        print(
                            f" SERIE -> Nodo: {nodo} | T.DS: {registro['temperaturaDS']}°C | "
                            f"Estado: {registro['estado']}"
                        )

                        # Reenviar a Render si se está ejecutando en local
                        if requests is not None:
                            try:
                                requests.post(URL_RENDER, json=registro, timeout=3)
                            except Exception:
                                pass

        except Exception as e:
            time.sleep(5)


# =====================================================
# RUTAS DE PÁGINA WEB Y API
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

@app.route("/logo-fain.jpg")
def logo_fain():
    return send_from_directory(".", "logo-fain.jpg")

@app.route("/logo-faca.jpg")
def logo_faca():
    return send_from_directory(".", "logo-faca.jpg")

@app.route("/datos", methods=["GET"])
def obtener_datos():
    return jsonify(datos_actuales)

@app.route("/historial", methods=["GET"])
def obtener_historial():
    return jsonify(historial)

@app.route("/api/archivos-csv", methods=["GET"])
def listar_archivos_csv():
    if not os.path.exists("registros"):
        return jsonify([])
    archivos = sorted(os.listdir("registros"), reverse=True)
    return jsonify([f for f in archivos if f.endswith(".csv")])

@app.route("/descargar/<nombre_archivo>")
def descargar_csv(nombre_archivo):
    return send_from_directory("registros", nombre_archivo, as_attachment=True)

@app.route("/api/medicion", methods=["POST"])
def recibir_medicion():
    from flask import request
    try:
        data = request.get_json()
        nodo = int(data.get("nodo", 1))

        if "fechaHora" not in data or not data["fechaHora"]:
            data["fechaHora"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Recalcular o asegurar estado si no viniera
        if "estado" not in data:
            data["estado"] = determinar_estado(
                float(data.get("temperaturaDS", 0)), float(data.get("puntoRocio", 0))
            )

        datos_actuales[nodo] = data
        historial.append(data)
        guardar_en_csv(data)

        return jsonify({"status": "ok", "message": "Datos recibidos correctamente"}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400


# =====================================================
# INICIO DEL SERVIDOR (MQTT + SERIE + FLASK)
# =====================================================
if __name__ == "__main__":
    # Hilo 1: Escucha constante a HiveMQ Cloud (LoRa / Dragino)
    hilo_mqtt = threading.Thread(target=iniciar_mqtt, daemon=True)
    hilo_mqtt.start()

    # Hilo 2: Escucha puerto Serie local USB (COM3)
    hilo_serie = threading.Thread(target=leer_esp32_serie, daemon=True)
    hilo_serie.start()

    port = int(os.environ.get("PORT", 5000))

    print("\n========================================")
    print("      SERVIDOR WEB - MONITOREO HELADAS  ")
    print("========================================\n")
    print(" -> Escuchando MQTT en HiveMQ Cloud")
    print(f" -> Escuchando Puerto Serie local ({PUERTO_SERIE})")
    print(f" -> Servidor corriendo en puerto: {port}")
    print("========================================\n")

    app.run(host="0.0.0.0", port=port)
