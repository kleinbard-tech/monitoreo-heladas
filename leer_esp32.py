import csv
import os
import threading
import time
import math
from datetime import datetime, timezone, timedelta

import requests

from flask import Flask, jsonify, send_from_directory


# =====================================================
# CONFIGURACIÓN
# =====================================================

# Canal de ThingSpeak
THINGSPEAK_CHANNEL_ID = "3506543"

# Si el canal de ThingSpeak es público, dejar vacío.
# Si posteriormente lo hacemos privado, colocar aquí
# la READ API KEY mediante una variable de entorno.
THINGSPEAK_READ_API_KEY = os.environ.get(
    "THINGSPEAK_READ_API_KEY",
    ""
)

# Cada cuánto consultar ThingSpeak.
#
# ThingSpeak tiene limitaciones de frecuencia para las
# actualizaciones de canales. 20 segundos es un intervalo
# seguro para este proyecto.
INTERVALO_THINGSPEAK = 20


# =====================================================
# CONFIGURACIÓN DE FLASK
# =====================================================

app = Flask(__name__)


# =====================================================
# MEMORIA DE DATOS
# =====================================================

# Guarda el último dato disponible de cada nodo.
#
# Ejemplo:
#
# datos_actuales = {
#     1: {
#         ...
#     }
# }
#
datos_actuales = {}


# Guarda el historial recibido durante la ejecución
# actual del servidor.
historial = []


# Guarda el ID de ThingSpeak que ya procesamos.
#
# Esto es importante para no guardar varias veces
# el mismo registro en el CSV.
ultimo_entry_id_procesado = None


# =====================================================
# CÁLCULO DEL PUNTO DE ROCÍO
# =====================================================

def calcular_punto_rocio(temperatura, humedad):
    """
    Calcula el punto de rocío mediante la aproximación
    de Magnus-Tetens.

    temperatura -> temperatura en °C
    humedad     -> humedad relativa en %

    Devuelve el punto de rocío en °C.
    """

    try:

        # Constantes utilizadas para la aproximación
        a = 17.27
        b = 237.7

        # Evitamos valores inválidos
        if humedad <= 0:
            return None

        if humedad > 100:
            humedad = 100

        alpha = (
            (a * temperatura) / (b + temperatura)
            + math.log(humedad / 100.0)
        )

        punto_rocio = (
            (b * alpha) /
            (a - alpha)
        )

        return punto_rocio

    except Exception as e:

        print(f"⚠ Error calculando punto de rocío: {e}")

        return None


# =====================================================
# DETERMINAR ESTADO AMBIENTAL
# =====================================================

def determinar_estado(temperatura_ds, punto_rocio):
    """
    Determina el estado ambiental según la temperatura
    medida por el DS18B20 y el punto de rocío.
    """

    if punto_rocio is None:
        return "NORMAL"

    # Helada
    if temperatura_ds <= 0.0:
        return "HELADA"

    # Situación de riesgo
    diferencia = temperatura_ds - punto_rocio

    if temperatura_ds <= 3.0 and diferencia <= 2.0:
        return "RIESGO"

    # Situación normal
    return "NORMAL"


# =====================================================
# CONVERTIR FECHA DE THINGSPEAK
# =====================================================

def convertir_fecha_thingspeak(fecha_texto):
    """
    ThingSpeak entrega normalmente la fecha en UTC,
    por ejemplo:

    2026-09-23T23:20:15Z

    La convertimos a hora local de Argentina (UTC-3).
    """

    try:

        fecha_utc = datetime.fromisoformat(
            fecha_texto.replace("Z", "+00:00")
        )

        zona_argentina = timezone(
            timedelta(hours=-3)
        )

        fecha_local = fecha_utc.astimezone(
            zona_argentina
        )

        return fecha_local.strftime(
            "%Y-%m-%d %H:%M:%S"
        )

    except Exception:

        # Si por alguna razón ThingSpeak entrega
        # un formato inesperado, usamos la hora local
        # del servidor.
        return datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        )


# =====================================================
# GUARDAR EN CSV MENSUAL
# =====================================================

def guardar_en_csv(registro):

    try:

        # Crear carpeta si no existe
        if not os.path.exists("registros"):
            os.makedirs("registros")

        # Obtener fecha
        fecha = registro.get(
            "fechaHora",
            ""
        )

        if not fecha:
            return

        # Obtener año y mes
        anio_mes = fecha[:7]

        nombre_archivo = (
            f"registros/historial_{anio_mes}.csv"
        )

        archivo_existe = os.path.exists(
            nombre_archivo
        )

        with open(
            nombre_archivo,
            mode="a",
            newline="",
            encoding="utf-8"
        ) as archivo:

            writer = csv.writer(archivo)

            # Escribir encabezado solamente
            # si el archivo es nuevo
            if not archivo_existe:

                writer.writerow([
                    "FechaHora",
                    "Nodo",
                    "Medicion",
                    "TemperaturaDS",
                    "TemperaturaDHT",
                    "Humedad",
                    "PuntoRocio",
                    "Estado"
                ])

            writer.writerow([

                registro.get(
                    "fechaHora",
                    ""
                ),

                registro.get(
                    "nodo",
                    1
                ),

                registro.get(
                    "medicion",
                    0
                ),

                registro.get(
                    "temperaturaDS",
                    0.0
                ),

                registro.get(
                    "temperaturaDHT",
                    0.0
                ),

                registro.get(
                    "humedad",
                    0.0
                ),

                registro.get(
                    "puntoRocio",
                    0.0
                ),

                registro.get(
                    "estado",
                    "NORMAL"
                )
            ])

        print(
            f"✓ Registro guardado en {nombre_archivo}"
        )

    except Exception as e:

        print(
            f"⚠ Error al guardar en CSV: {e}"
        )


# =====================================================
# PROCESAR REGISTRO DE THINGSPEAK
# =====================================================

def procesar_registro_thingspeak(registro_ts):
    """
    Recibe un registro individual de ThingSpeak.

    Para Nodo 1:

    field1 -> DS18B20
    field2 -> DHT22
    field3 -> Humedad

    Devuelve el diccionario que utiliza el resto
    de la aplicación.
    """

    try:

        # -------------------------------------------------
        # Obtener campos de ThingSpeak
        # -------------------------------------------------

        field1 = registro_ts.get("field1")
        field2 = registro_ts.get("field2")
        field3 = registro_ts.get("field3")

        # Verificar que existan los tres valores
        if field1 is None:
            print("⚠ ThingSpeak: Field 1 vacío")
            return None

        if field2 is None:
            print("⚠ ThingSpeak: Field 2 vacío")
            return None

        if field3 is None:
            print("⚠ ThingSpeak: Field 3 vacío")
            return None

        # Convertir valores
        temperatura_ds = float(field1)
        temperatura_dht = float(field2)
        humedad = float(field3)

        # -------------------------------------------------
        # Calcular punto de rocío
        # -------------------------------------------------

        punto_rocio = calcular_punto_rocio(
            temperatura_dht,
            humedad
        )

        # -------------------------------------------------
        # Determinar estado
        # -------------------------------------------------

        estado = determinar_estado(
            temperatura_ds,
            punto_rocio
        )

        # -------------------------------------------------
        # Fecha
        # -------------------------------------------------

        fecha_hora = convertir_fecha_thingspeak(
            registro_ts.get("created_at", "")
        )

        # -------------------------------------------------
        # Entry ID de ThingSpeak
        #
        # Lo utilizamos como número de medición.
        # -------------------------------------------------

        medicion = int(
            registro_ts.get(
                "entry_id",
                0
            )
        )

        # -------------------------------------------------
        # Crear registro
        # -------------------------------------------------

        registro = {

            "fechaHora": fecha_hora,

            "nodo": 1,

            "medicion": medicion,

            "temperaturaDS": temperatura_ds,

            "temperaturaDHT": temperatura_dht,

            "humedad": humedad,

            "puntoRocio": punto_rocio,

            "estado": estado,

            "conectado": True
        }

        return registro

    except Exception as e:

        print(
            f"⚠ Error procesando registro "
            f"de ThingSpeak: {e}"
        )

        return None


# =====================================================
# CONSULTAR THINGSPEAK
# =====================================================

def consultar_thingspeak():

    global ultimo_entry_id_procesado

    print("\n========================================")
    print("   LECTOR THINGSPEAK - NODO 1")
    print("========================================")
    print(
        f"Canal: {THINGSPEAK_CHANNEL_ID}"
    )
    print(
        f"Intervalo: {INTERVALO_THINGSPEAK} segundos"
    )
    print("========================================\n")

    while True:

        try:

            # -------------------------------------------------
            # URL de la API
            # -------------------------------------------------

            url = (
                "https://api.thingspeak.com/"
                f"channels/{THINGSPEAK_CHANNEL_ID}/feeds.json"
            )

            # -------------------------------------------------
            # Parámetros
            #
            # results=1 significa que solamente pedimos
            # el último registro.
            # -------------------------------------------------

            parametros = {
                "results": 1
            }

            # Si existe una READ API KEY, la utilizamos.
            if THINGSPEAK_READ_API_KEY:

                parametros["api_key"] = (
                    THINGSPEAK_READ_API_KEY
                )

            # -------------------------------------------------
            # Realizar consulta
            # -------------------------------------------------

            respuesta = requests.get(
                url,
                params=parametros,
                timeout=10
            )

            # Verificar HTTP
            respuesta.raise_for_status()

            datos = respuesta.json()

            # -------------------------------------------------
            # Verificar que haya feeds
            # -------------------------------------------------

            feeds = datos.get(
                "feeds",
                []
            )

            if not feeds:

                print(
                    "⚠ ThingSpeak no devolvió registros."
                )

                time.sleep(
                    INTERVALO_THINGSPEAK
                )

                continue

            # -------------------------------------------------
            # Obtener último registro
            # -------------------------------------------------

            registro_ts = feeds[0]

            entry_id = int(
                registro_ts.get(
                    "entry_id",
                    0
                )
            )

            # -------------------------------------------------
            # Evitar procesar nuevamente
            # el mismo registro
            # -------------------------------------------------

            if (
                ultimo_entry_id_procesado
                == entry_id
            ):

                print(
                    f"ThingSpeak: sin datos nuevos "
                    f"(Entry ID {entry_id})"
                )

                time.sleep(
                    INTERVALO_THINGSPEAK
                )

                continue

            # -------------------------------------------------
            # Procesar registro
            # -------------------------------------------------

            registro = procesar_registro_thingspeak(
                registro_ts
            )

            if registro is not None:

                # Actualizar Nodo 1
                datos_actuales[1] = registro

                # Agregar al historial
                historial.append(
                    registro
                )

                # Guardar CSV
                guardar_en_csv(
                    registro
                )

                # Guardar Entry ID
                ultimo_entry_id_procesado = (
                    entry_id
                )

                # Mostrar información
                print(
                    "\n✓ NUEVA MEDICIÓN"
                )

                print(
                    f"  Entry ID: {entry_id}"
                )

                print(
                    f"  Fecha: "
                    f"{registro['fechaHora']}"
                )

                print(
                    f"  Nodo: "
                    f"{registro['nodo']}"
                )

                print(
                    f"  DS18B20: "
                    f"{registro['temperaturaDS']:.2f} °C"
                )

                print(
                    f"  DHT22: "
                    f"{registro['temperaturaDHT']:.2f} °C"
                )

                print(
                    f"  Humedad: "
                    f"{registro['humedad']:.2f} %"
                )

                if registro["puntoRocio"] is not None:

                    print(
                        f"  Punto de rocío: "
                        f"{registro['puntoRocio']:.2f} °C"
                    )

                print(
                    f"  Estado: "
                    f"{registro['estado']}"
                )

            # -------------------------------------------------
            # Esperar próxima consulta
            # -------------------------------------------------

            time.sleep(
                INTERVALO_THINGSPEAK
            )

        except requests.exceptions.RequestException as e:

            print(
                f"⚠ Error HTTP consultando "
                f"ThingSpeak: {e}"
            )

            time.sleep(
                INTERVALO_THINGSPEAK
            )

        except Exception as e:

            print(
                f"⚠ Error en lector ThingSpeak: {e}"
            )

            time.sleep(
                INTERVALO_THINGSPEAK
            )


# =====================================================
# RUTAS DE LA PÁGINA WEB
# =====================================================

@app.route("/")
def pagina_principal():

    return send_from_directory(
        ".",
        "index.html"
    )


@app.route("/estilo.css")
def estilo():

    return send_from_directory(
        ".",
        "estilo.css"
    )


@app.route("/script.js")
def javascript():

    return send_from_directory(
        ".",
        "script.js"
    )


# =====================================================
# LOGOS
# =====================================================

@app.route("/logo-unco.jpg")
def logo_unco():

    return send_from_directory(
        ".",
        "logo-unco.jpg"
    )


@app.route("/logo-fain.jpg")
def logo_fain():

    return send_from_directory(
        ".",
        "logo-fain.jpg"
    )


@app.route("/logo-faca.jpg")
def logo_faca():

    return send_from_directory(
        ".",
        "logo-faca.jpg"
    )


# =====================================================
# API - DATOS ACTUALES
# =====================================================

@app.route(
    "/datos",
    methods=["GET"]
)
def obtener_datos():

    return jsonify(
        datos_actuales
    )


# =====================================================
# API - HISTORIAL
# =====================================================

@app.route(
    "/historial",
    methods=["GET"]
)
def obtener_historial():

    return jsonify(
        historial
    )


# =====================================================
# API - LISTAR CSV
# =====================================================

@app.route(
    "/api/archivos-csv",
    methods=["GET"]
)
def listar_archivos_csv():

    if not os.path.exists(
        "registros"
    ):

        return jsonify([])

    archivos = sorted(
        os.listdir("registros"),
        reverse=True
    )

    archivos_csv = []

    for archivo in archivos:

        if archivo.endswith(".csv"):

            archivos_csv.append(
                archivo
            )

    return jsonify(
        archivos_csv
    )


# =====================================================
# DESCARGAR CSV
# =====================================================

@app.route(
    "/descargar/<nombre_archivo>"
)
def descargar_csv(
    nombre_archivo
):

    return send_from_directory(
        "registros",
        nombre_archivo,
        as_attachment=True
    )


# =====================================================
# API - RECEPCIÓN MANUAL
#
# La mantenemos para no romper la arquitectura
# existente. Puede servir posteriormente para
# pruebas o para enviar datos desde otro equipo.
# =====================================================

@app.route(
    "/api/medicion",
    methods=["POST"]
)
def recibir_medicion():

    from flask import request

    try:

        data = request.get_json()

        nodo = int(
            data.get(
                "nodo",
                1
            )
        )

        # Fecha
        if (
            "fechaHora" not in data
            or not data["fechaHora"]
        ):

            data["fechaHora"] = (
                datetime.now().strftime(
                    "%Y-%m-%d %H:%M:%S"
                )
            )

        # Convertir valores numéricos
        temperatura_ds = float(
            data.get(
                "temperaturaDS",
                0
            )
        )

        temperatura_dht = float(
            data.get(
                "temperaturaDHT",
                0
            )
        )

        humedad = float(
            data.get(
                "humedad",
                0
            )
        )

        # Si no viene punto de rocío,
        # lo calculamos.
        if (
            "puntoRocio" not in data
            or data["puntoRocio"] is None
        ):

            data["puntoRocio"] = (
                calcular_punto_rocio(
                    temperatura_dht,
                    humedad
                )
            )

        # Si no viene estado,
        # lo calculamos.
        if (
            "estado" not in data
            or not data["estado"]
        ):

            data["estado"] = (
                determinar_estado(
                    temperatura_ds,
                    data["puntoRocio"]
                )
            )

        # Marcar conexión
        data["conectado"] = True

        # Actualizar nodo
        datos_actuales[nodo] = data

        # Historial
        historial.append(
            data
        )

        # CSV
        guardar_en_csv(
            data
        )

        return jsonify({
            "status": "ok",
            "message":
                "Datos recibidos correctamente"
        }), 200

    except Exception as e:

        return jsonify({
            "status": "error",
            "message": str(e)
        }), 400


# =====================================================
# INICIO DEL SERVIDOR
# =====================================================

if __name__ == "__main__":

    # -------------------------------------------------
    # Hilo de ThingSpeak
    # -------------------------------------------------

    hilo_thingspeak = threading.Thread(
        target=consultar_thingspeak,
        daemon=True
    )

    hilo_thingspeak.start()

    # -------------------------------------------------
    # Puerto de Flask
    #
    # Render proporciona PORT mediante variable
    # de entorno.
    # -------------------------------------------------

    port = int(
        os.environ.get(
            "PORT",
            5000
        )
    )

    print("\n========================================")
    print("   SERVIDOR WEB - MONITOREO HELADAS")
    print("========================================")
    print("")
    print(
        " -> Fuente de datos: ThingSpeak"
    )
    print(
        f" -> Canal: {THINGSPEAK_CHANNEL_ID}"
    )
    print(
        " -> Nodo activo: Nodo 1"
    )
    print(
        " -> Flask escuchando en puerto:",
        port
    )
    print("========================================\n")

    # -------------------------------------------------
    # Iniciar Flask
    # -------------------------------------------------

    app.run(
        host="0.0.0.0",
        port=port
    )

