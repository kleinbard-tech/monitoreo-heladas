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

THINGSPEAK_CHANNEL_ID = "3506543"

THINGSPEAK_READ_API_KEY = os.environ.get(
    "THINGSPEAK_READ_API_KEY",
    ""
)

INTERVALO_THINGSPEAK = 20

# Tiempo máximo sin recibir datos antes de considerar
# desconectado el nodo.
#
# El nodo transmite cada 5 minutos,
# por eso dejamos 10 minutos de margen.
TIEMPO_DESCONEXION = 600


# =====================================================
# CONFIGURACIÓN DEL GRÁFICO
# =====================================================

# El gráfico mostrará solamente las últimas 12 horas.
HORAS_GRAFICO = 12

# El gráfico mostrará como máximo un punto cada 5 minutos.
#
# IMPORTANTE:
# Esto NO afecta al CSV.
# El CSV continúa guardando TODAS las mediciones.
INTERVALO_GRAFICO_MINUTOS = 5


# =====================================================
# CONFIGURACIÓN DE FLASK
# =====================================================

app = Flask(__name__)


# =====================================================
# MEMORIA DE DATOS
# =====================================================

datos_actuales = {}

historial = []

ultimo_entry_id_procesado = None

# Guarda el momento en que se recibió el último
# registro válido de cada nodo.
ultima_recepcion_nodo = {}


# =====================================================
# ENTRY IDS GUARDADOS EN CSV
# =====================================================

entry_ids_csv = set()


# =====================================================
# CÁLCULO DEL PUNTO DE ROCÍO
# =====================================================

def calcular_punto_rocio(temperatura, humedad):

    try:

        a = 17.27
        b = 237.7

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

        print(
            f"⚠ Error calculando punto de rocío: {e}"
        )

        return None


# =====================================================
# DETERMINAR ESTADO AMBIENTAL
# =====================================================

def determinar_estado(
    temperatura_ds,
    punto_rocio
):

    if punto_rocio is None:

        return "NORMAL"

    if temperatura_ds <= 0.0:

        return "HELADA"

    diferencia = (
        temperatura_ds -
        punto_rocio
    )

    if (
        temperatura_ds <= 3.0
        and diferencia <= 2.0
    ):

        return "RIESGO"

    return "NORMAL"


# =====================================================
# CONVERTIR FECHA DE THINGSPEAK
# =====================================================

def convertir_fecha_thingspeak(fecha_texto):

    try:

        fecha_utc = datetime.fromisoformat(
            fecha_texto.replace(
                "Z",
                "+00:00"
            )
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

        return datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        )


# =====================================================
# OBTENER DATETIME UTC DE THINGSPEAK
# =====================================================

def obtener_datetime_thingspeak(fecha_texto):

    try:

        fecha_utc = datetime.fromisoformat(
            fecha_texto.replace(
                "Z",
                "+00:00"
            )
        )

        return fecha_utc

    except Exception:

        return None


# =====================================================
# CORREGIR CSV EXISTENTES
# =====================================================

def corregir_csv_existentes():

    carpeta = "registros"

    if not os.path.exists(carpeta):

        return

    for nombre_archivo in os.listdir(carpeta):

        if not nombre_archivo.endswith(".csv"):

            continue

        ruta = os.path.join(
            carpeta,
            nombre_archivo
        )

        try:

            with open(
                ruta,
                mode="r",
                encoding="utf-8-sig",
                newline=""
            ) as archivo:

                contenido = archivo.read()

            if not contenido.strip():

                continue

            if ";" in contenido:

                print(
                    f"✓ CSV ya corregido: "
                    f"{nombre_archivo}"
                )

                continue

            ruta_temporal = (
                ruta +
                ".tmp"
            )

            with open(
                ruta,
                mode="r",
                encoding="utf-8-sig",
                newline=""
            ) as archivo_entrada:

                lector = csv.reader(
                    archivo_entrada,
                    delimiter=","
                )

                with open(
                    ruta_temporal,
                    mode="w",
                    encoding="utf-8-sig",
                    newline=""
                ) as archivo_salida:

                    escritor = csv.writer(
                        archivo_salida,
                        delimiter=";"
                    )

                    for fila in lector:

                        escritor.writerow(fila)

            os.replace(
                ruta_temporal,
                ruta
            )

            print(
                f"✓ CSV convertido: "
                f"{nombre_archivo}"
            )

        except Exception as e:

            print(
                f"⚠ Error convirtiendo "
                f"{nombre_archivo}: {e}"
            )

            ruta_temporal = (
                ruta +
                ".tmp"
            )

            if os.path.exists(
                ruta_temporal
            ):

                try:

                    os.remove(
                        ruta_temporal
                    )

                except Exception:

                    pass


# =====================================================
# OBTENER ENTRY IDS YA GUARDADOS EN LOS CSV
# =====================================================

def obtener_entry_ids_csv():

    ids = set()

    carpeta = "registros"

    if not os.path.exists(carpeta):

        return ids

    for nombre_archivo in os.listdir(carpeta):

        if not nombre_archivo.endswith(".csv"):

            continue

        ruta = os.path.join(
            carpeta,
            nombre_archivo
        )

        try:

            with open(
                ruta,
                mode="r",
                encoding="utf-8-sig",
                newline=""
            ) as archivo:

                lector = csv.DictReader(
                    archivo,
                    delimiter=";"
                )

                for fila in lector:

                    medicion = fila.get(
                        "Medicion"
                    )

                    if medicion:

                        try:

                            ids.add(
                                int(medicion)
                            )

                        except Exception:

                            pass

        except Exception as e:

            print(
                f"⚠ Error leyendo "
                f"{nombre_archivo}: {e}"
            )

    print(
        f"✓ Entry IDs existentes en CSV: "
        f"{len(ids)}"
    )

    return ids


# =====================================================
# GUARDAR EN CSV MENSUAL
# =====================================================

def guardar_en_csv(registro):

    global entry_ids_csv

    try:

        medicion = registro.get(
            "medicion"
        )

        try:

            medicion_int = int(
                medicion
            )

        except Exception:

            medicion_int = None

        if (
            medicion_int is not None
            and medicion_int in entry_ids_csv
        ):

            return

        if not os.path.exists(
            "registros"
        ):

            os.makedirs(
                "registros"
            )

        fecha = registro.get(
            "fechaHora",
            ""
        )

        if not fecha:

            return

        anio_mes = fecha[:7]

        nombre_archivo = (
            f"registros/"
            f"historial_{anio_mes}.csv"
        )

        archivo_existe = os.path.exists(
            nombre_archivo
        )

        with open(
            nombre_archivo,
            mode="a",
            newline="",
            encoding="utf-8-sig"
        ) as archivo:

            escritor = csv.writer(
                archivo,
                delimiter=";"
            )

            if not archivo_existe:

                escritor.writerow([
                    "FechaHora",
                    "Nodo",
                    "Medicion",
                    "TemperaturaDS",
                    "TemperaturaDHT",
                    "Humedad",
                    "PuntoRocio",
                    "Estado"
                ])

            def numero_csv(valor):

                if valor is None:

                    return ""

                try:

                    return (
                        f"{float(valor):.2f}"
                        .replace(".", ",")
                    )

                except Exception:

                    return ""

            escritor.writerow([

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

                numero_csv(
                    registro.get(
                        "temperaturaDS"
                    )
                ),

                numero_csv(
                    registro.get(
                        "temperaturaDHT"
                    )
                ),

                numero_csv(
                    registro.get(
                        "humedad"
                    )
                ),

                numero_csv(
                    registro.get(
                        "puntoRocio"
                    )
                ),

                registro.get(
                    "estado",
                    "NORMAL"
                )
            ])

        if medicion_int is not None:

            entry_ids_csv.add(
                medicion_int
            )

        print(
            f"✓ Registro guardado en "
            f"{nombre_archivo}"
        )

    except Exception as e:

        print(
            f"⚠ Error al guardar en CSV: {e}"
        )


# =====================================================
# PROCESAR REGISTRO DE THINGSPEAK
# =====================================================

def procesar_registro_thingspeak(
    registro_ts
):

    try:

        field1 = registro_ts.get(
            "field1"
        )

        field2 = registro_ts.get(
            "field2"
        )

        field3 = registro_ts.get(
            "field3"
        )

        if field1 is None:

            print(
                "⚠ ThingSpeak: "
                "Field 1 vacío"
            )

            return None

        if field2 is None:

            print(
                "⚠ ThingSpeak: "
                "Field 2 vacío"
            )

            return None

        if field3 is None:

            print(
                "⚠ ThingSpeak: "
                "Field 3 vacío"
            )

            return None

        temperatura_ds = float(
            field1
        )

        temperatura_dht = float(
            field2
        )

        humedad = float(
            field3
        )

        punto_rocio = calcular_punto_rocio(
            temperatura_dht,
            humedad
        )

        estado = determinar_estado(
            temperatura_ds,
            punto_rocio
        )

        fecha_hora = convertir_fecha_thingspeak(
            registro_ts.get(
                "created_at",
                ""
            )
        )

        medicion = int(
            registro_ts.get(
                "entry_id",
                0
            )
        )

        registro = {

            "fechaHora":
                fecha_hora,

            "nodo":
                1,

            "medicion":
                medicion,

            "temperaturaDS":
                temperatura_ds,

            "temperaturaDHT":
                temperatura_dht,

            "humedad":
                humedad,

            "puntoRocio":
                punto_rocio,

            "estado":
                estado,

            "conectado":
                True
        }

        return registro

    except Exception as e:

        print(
            f"⚠ Error procesando registro "
            f"de ThingSpeak: {e}"
        )

        return None


# =====================================================
# CARGAR HISTORIAL DE THINGSPEAK AL INICIAR
# =====================================================

def cargar_historial_inicial():

    global ultimo_entry_id_procesado

    print(
        "\n========================================"
    )

    print(
        "   CARGANDO HISTORIAL DE THINGSPEAK"
    )

    print(
        "========================================"
    )

    try:

        url = (
            "https://api.thingspeak.com/"
            f"channels/"
            f"{THINGSPEAK_CHANNEL_ID}/"
            "feeds.json"
        )

        parametros = {
            "results": 8000
        }

        if THINGSPEAK_READ_API_KEY:

            parametros["api_key"] = (
                THINGSPEAK_READ_API_KEY
            )

        respuesta = requests.get(
            url,
            params=parametros,
            timeout=20
        )

        respuesta.raise_for_status()

        datos = respuesta.json()

        feeds = datos.get(
            "feeds",
            []
        )

        if not feeds:

            print(
                "⚠ No hay registros históricos "
                "en ThingSpeak."
            )

            datos_actuales[1] = {

                "nodo": 1,

                "conectado": False,

                "estado": "NORMAL",

                "mensaje": "Sin datos"
            }

            return

        print(
            f"✓ ThingSpeak devolvió "
            f"{len(feeds)} registros."
        )

        registros_cargados = 0

        ultimo_registro = None

        for feed in feeds:

            registro = (
                procesar_registro_thingspeak(
                    feed
                )
            )

            if registro is None:

                continue

            registros_cargados += 1

            ultimo_registro = registro

            historial.append(
                registro
            )

            guardar_en_csv(
                registro
            )

        if len(historial) > 1000:

            historial[:] = historial[-1000:]

        if ultimo_registro is not None:

            ultimo_entry_id_procesado = (
                ultimo_registro["medicion"]
            )

            datos_actuales[1] = (
                ultimo_registro
            )

            feed_fecha = feeds[-1].get(
                "created_at",
                ""
            )

            fecha_ultimo_dato = (
                obtener_datetime_thingspeak(
                    feed_fecha
                )
            )

            if fecha_ultimo_dato is not None:

                ahora_utc = datetime.now(
                    timezone.utc
                )

                segundos_desde_ultimo = (
                    ahora_utc -
                    fecha_ultimo_dato
                ).total_seconds()

                if (
                    segundos_desde_ultimo
                    <= TIEMPO_DESCONEXION
                ):

                    datos_actuales[1][
                        "conectado"
                    ] = True

                    ultima_recepcion_nodo[1] = (
                        time.time()
                        - segundos_desde_ultimo
                    )

                    print(
                        "✓ Nodo 1: CONECTADO"
                    )

                else:

                    datos_actuales[1][
                        "conectado"
                    ] = False

                    print(
                        "⚠ Nodo 1: DESCONECTADO"
                    )

            else:

                datos_actuales[1][
                    "conectado"
                ] = False

        print(
            f"✓ Registros cargados en memoria: "
            f"{len(historial)}"
        )

        print(
            f"✓ Registros procesados: "
            f"{registros_cargados}"
        )

        print(
            f"✓ Último Entry ID: "
            f"{ultimo_entry_id_procesado}"
        )

        print(
            "========================================\n"
        )

    except requests.exceptions.RequestException as e:

        print(
            f"⚠ Error cargando historial "
            f"de ThingSpeak: {e}"
        )

    except Exception as e:

        print(
            f"⚠ Error cargando historial: {e}"
        )


# =====================================================
# ACTUALIZAR ESTADO DE CONEXIÓN
# =====================================================

def actualizar_estado_conexion():

    print(
        "✓ Monitor de conexión iniciado"
    )

    while True:

        try:

            ahora = time.time()

            nodo = 1

            if nodo in ultima_recepcion_nodo:

                tiempo_sin_datos = (
                    ahora -
                    ultima_recepcion_nodo[nodo]
                )

                if (
                    tiempo_sin_datos
                    > TIEMPO_DESCONEXION
                ):

                    if nodo in datos_actuales:

                        datos_actuales[nodo][
                            "conectado"
                        ] = False

            else:

                if nodo in datos_actuales:

                    datos_actuales[nodo][
                        "conectado"
                    ] = False

            time.sleep(10)

        except Exception as e:

            print(
                f"⚠ Error monitorizando "
                f"conexión: {e}"
            )

            time.sleep(10)


# =====================================================
# CONSULTAR THINGSPEAK
# =====================================================

def consultar_thingspeak():

    global ultimo_entry_id_procesado

    print(
        "\n========================================"
    )

    print(
        "   LECTOR THINGSPEAK - NODO 1"
    )

    print(
        "========================================"
    )

    print(
        f"Canal: "
        f"{THINGSPEAK_CHANNEL_ID}"
    )

    print(
        f"Intervalo: "
        f"{INTERVALO_THINGSPEAK} segundos"
    )

    print(
        f"Desconexión después de: "
        f"{TIEMPO_DESCONEXION // 60} minutos"
    )

    print(
        "========================================\n"
    )

    while True:

        try:

            url = (
                "https://api.thingspeak.com/"
                f"channels/"
                f"{THINGSPEAK_CHANNEL_ID}/"
                "feeds.json"
            )

            parametros = {
                "results": 1
            }

            if THINGSPEAK_READ_API_KEY:

                parametros["api_key"] = (
                    THINGSPEAK_READ_API_KEY
                )

            respuesta = requests.get(
                url,
                params=parametros,
                timeout=10
            )

            respuesta.raise_for_status()

            datos = respuesta.json()

            feeds = datos.get(
                "feeds",
                []
            )

            if not feeds:

                print(
                    "⚠ ThingSpeak no devolvió "
                    "registros."
                )

                time.sleep(
                    INTERVALO_THINGSPEAK
                )

                continue

            registro_ts = feeds[0]

            entry_id = int(
                registro_ts.get(
                    "entry_id",
                    0
                )
            )

            if (
                ultimo_entry_id_procesado
                == entry_id
            ):

                print(
                    f"ThingSpeak: "
                    f"sin datos nuevos "
                    f"(Entry ID "
                    f"{entry_id})"
                )

                time.sleep(
                    INTERVALO_THINGSPEAK
                )

                continue

            registro = (
                procesar_registro_thingspeak(
                    registro_ts
                )
            )

            if registro is not None:

                datos_actuales[1] = (
                    registro
                )

                datos_actuales[1][
                    "conectado"
                ] = True

                ultima_recepcion_nodo[1] = (
                    time.time()
                )

                historial.append(
                    registro
                )

                if len(historial) > 1000:

                    del historial[
                        :-1000
                    ]

                guardar_en_csv(
                    registro
                )

                ultimo_entry_id_procesado = (
                    entry_id
                )

                print(
                    "\n✓ NUEVA MEDICIÓN"
                )

                print(
                    f"  Entry ID: "
                    f"{entry_id}"
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
                    f"{registro['temperaturaDS']:.2f}"
                    f" °C"
                )

                print(
                    f"  DHT22: "
                    f"{registro['temperaturaDHT']:.2f}"
                    f" °C"
                )

                print(
                    f"  Humedad: "
                    f"{registro['humedad']:.2f}"
                    f" %"
                )

                if (
                    registro["puntoRocio"]
                    is not None
                ):

                    print(
                        f"  Punto de rocío: "
                        f"{registro['puntoRocio']:.2f}"
                        f" °C"
                    )

                print(
                    f"  Estado: "
                    f"{registro['estado']}"
                )

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
                f"⚠ Error en lector "
                f"ThingSpeak: {e}"
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
# DATOS ACTUALES
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
# HISTORIAL PARA EL GRÁFICO
# =====================================================

@app.route(
    "/historial",
    methods=["GET"]
)
def obtener_historial():

    # =================================================
    # PASO 1:
    # TOMAR SOLAMENTE LAS ÚLTIMAS 12 HORAS
    # =================================================

    ahora = datetime.now()

    limite = (
        ahora -
        timedelta(hours=HORAS_GRAFICO)
    )

    historial_12_horas = []

    for registro in historial:

        try:

            fecha_texto = registro.get(
                "fechaHora",
                ""
            )

            fecha_registro = datetime.strptime(
                fecha_texto,
                "%Y-%m-%d %H:%M:%S"
            )

            if fecha_registro >= limite:

                historial_12_horas.append(
                    registro
                )

        except Exception:

            continue


    # =================================================
    # PASO 2:
    # MOSTRAR SOLO UN PUNTO CADA 5 MINUTOS
    # =================================================

    historial_grafico = []

    ultima_fecha_mostrada = None

    intervalo = timedelta(
        minutes=INTERVALO_GRAFICO_MINUTOS
    )

    for registro in historial_12_horas:

        try:

            fecha_texto = registro.get(
                "fechaHora",
                ""
            )

            fecha_registro = datetime.strptime(
                fecha_texto,
                "%Y-%m-%d %H:%M:%S"
            )

            # Si es el primer registro,
            # lo agregamos.

            if ultima_fecha_mostrada is None:

                historial_grafico.append(
                    registro
                )

                ultima_fecha_mostrada = (
                    fecha_registro
                )

                continue


            # Comprobar si pasaron al menos
            # 5 minutos desde el último
            # punto mostrado.

            diferencia = (
                fecha_registro -
                ultima_fecha_mostrada
            )

            if diferencia >= intervalo:

                historial_grafico.append(
                    registro
                )

                ultima_fecha_mostrada = (
                    fecha_registro
                )

        except Exception:

            continue


    return jsonify(
        historial_grafico
    )


# =====================================================
# LISTAR ARCHIVOS CSV
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
# RECIBIR MEDICIÓN POR POST
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

        if (
            "fechaHora" not in data
            or not data["fechaHora"]
        ):

            data["fechaHora"] = (
                datetime.now().strftime(
                    "%Y-%m-%d %H:%M:%S"
                )
            )

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

        data["conectado"] = True

        ultima_recepcion_nodo[nodo] = (
            time.time()
        )

        datos_actuales[nodo] = data

        historial.append(
            data
        )

        guardar_en_csv(
            data
        )

        return jsonify({

            "status":
                "ok",

            "message":
                "Datos recibidos correctamente"

        }), 200

    except Exception as e:

        return jsonify({

            "status":
                "error",

            "message":
                str(e)

        }), 400


# =====================================================
# INICIO DEL SERVIDOR
# =====================================================

if __name__ == "__main__":

    os.makedirs(
        "registros",
        exist_ok=True
    )

    corregir_csv_existentes()

    entry_ids_csv = (
        obtener_entry_ids_csv()
    )

    cargar_historial_inicial()

    hilo_thingspeak = threading.Thread(
        target=consultar_thingspeak,
        daemon=True
    )

    hilo_thingspeak.start()

    hilo_conexion = threading.Thread(
        target=actualizar_estado_conexion,
        daemon=True
    )

    hilo_conexion.start()

    port = int(
        os.environ.get(
            "PORT",
            5000
        )
    )

    print(
        "\n========================================"
    )

    print(
        "   SERVIDOR WEB - MONITOREO HELADAS"
    )

    print(
        "========================================"
    )

    print("")

    print(
        " -> Fuente de datos: ThingSpeak"
    )

    print(
        f" -> Canal: "
        f"{THINGSPEAK_CHANNEL_ID}"
    )

    print(
        " -> Nodo activo: Nodo 1"
    )

    print(
        " -> Historial ThingSpeak: hasta 8000 registros"
    )

    print(
        " -> CSV: separado por punto y coma (;)"
    )

    print(
        " -> CSV: números con coma decimal"
    )

    print(
        f" -> Gráfico: últimas "
        f"{HORAS_GRAFICO} horas"
    )

    print(
        f" -> Gráfico: 1 punto cada "
        f"{INTERVALO_GRAFICO_MINUTOS} minutos"
    )

    print(
        " -> Codificación: UTF-8-SIG"
    )

    print(
        f" -> Desconexión: "
        f"{TIEMPO_DESCONEXION // 60} minutos"
    )

    print(
        " -> Flask escuchando en puerto:",
        port
    )

    print(
        "========================================\n"
    )

    app.run(
        host="0.0.0.0",
        port=port
    )
