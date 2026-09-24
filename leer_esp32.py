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

# Python consulta ThingSpeak cada 20 segundos.
INTERVALO_THINGSPEAK = 20

# El nodo se considera desconectado después
# de 10 minutos sin recibir una medición.
TIEMPO_DESCONEXION = 600


# =====================================================
# CONFIGURACIÓN DE LOS REGISTROS
# =====================================================

# Los registros finales se generan cada 5 minutos.
INTERVALO_REGISTRO_MINUTOS = 5

# Permitimos utilizar una medición real que esté
# como máximo 2 minutos antes o después del horario
# objetivo.
#
# Ejemplo:
#
# Objetivo: 18:05
#
# Se pueden utilizar:
#
# 18:03
# 18:05
# 18:07
#
# La más cercana será la elegida.
TOLERANCIA_MEDICION_MINUTOS = 2


# =====================================================
# CONFIGURACIÓN DEL GRÁFICO
# =====================================================

# El gráfico muestra solamente las últimas 12 horas.
HORAS_GRAFICO = 12

# =====================================================
# CONFIGURACIÓN DE FLASK
# =====================================================

app = Flask(__name__)


# =====================================================
# MEMORIA DE DATOS
# =====================================================

# Último dato real recibido de cada nodo.
datos_actuales = {}

# Historial PROCESADO.
#
# IMPORTANTE:
# Acá no guardamos todas las mediciones de ThingSpeak.
#
# Guardamos solamente los registros de 5 minutos.
historial = []

# Último Entry ID que ya vimos de ThingSpeak.
ultimo_entry_id_procesado = None

# Momento real en que se recibió el último dato
# de cada nodo.
ultima_recepcion_nodo = {}


# =====================================================
# MEDICIONES REALES PENDIENTES
# =====================================================

# Acá almacenamos las mediciones reales recibidas
# desde ThingSpeak que todavía no fueron asignadas
# a un intervalo de 5 minutos.
#
# Ejemplo:
#
# 18:03
# 18:05
# 18:07
#
# Luego se utilizarán para generar:
#
# 18:05
#
# según cuál sea la más adecuada.
mediciones_pendientes = []


# =====================================================
# MEDICIONES YA UTILIZADAS
# =====================================================

# Guarda los Entry ID de ThingSpeak que ya fueron
# utilizados para generar un registro de 5 minutos.
#
# Esto evita utilizar una misma medición dos veces.
entry_ids_utilizados = set()


# =====================================================
# ÚLTIMO INTERVALO GENERADO
# =====================================================

ultimo_intervalo_generado = None


# =====================================================
# CÁLCULO DEL PUNTO DE ROCÍO
# =====================================================

def calcular_punto_rocio(
    temperatura,
    humedad
):

    try:

        a = 17.27
        b = 237.7

        if humedad <= 0:

            return None

        if humedad > 100:

            humedad = 100

        alpha = (
            (a * temperatura) /
            (b + temperatura)
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

def convertir_fecha_thingspeak(
    fecha_texto
):

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

        fecha_local = (
            fecha_utc.astimezone(
                zona_argentina
            )
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

def obtener_datetime_thingspeak(
    fecha_texto
):

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
# OBTENER DATETIME LOCAL
# =====================================================

def obtener_datetime_local(
    fecha_texto
):

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

        return fecha_utc.astimezone(
            zona_argentina
        ).replace(
            tzinfo=None
        )

    except Exception:

        return None


# =====================================================
# REDONDEAR HACIA ABAJO A INTERVALO DE 5 MINUTOS
# =====================================================

def obtener_intervalo_5_minutos(
    fecha
):

    minuto = (
        fecha.minute
        - (
            fecha.minute %
            INTERVALO_REGISTRO_MINUTOS
        )
    )

    return fecha.replace(
        minute=minuto,
        second=0,
        microsecond=0
    )


# =====================================================
# CONVERTIR NÚMERO PARA CSV
# =====================================================

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

            return None

        if field2 is None:

            return None

        if field3 is None:

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

        punto_rocio = (
            calcular_punto_rocio(
                temperatura_dht,
                humedad
            )
        )

        estado = (
            determinar_estado(
                temperatura_ds,
                punto_rocio
            )
        )

        fecha_hora = (
            convertir_fecha_thingspeak(
                registro_ts.get(
                    "created_at",
                    ""
                )
            )
        )

        fecha_real = (
            obtener_datetime_local(
                registro_ts.get(
                    "created_at",
                    ""
                )
            )
        )

        if fecha_real is None:

            return None

        medicion = int(
            registro_ts.get(
                "entry_id",
                0
            )
        )

        registro = {

            "fechaHora":
                fecha_hora,

            "fechaReal":
                fecha_real,

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
# GUARDAR REGISTRO PROCESADO EN CSV
# =====================================================

def guardar_en_csv(
    registro
):

    try:

        if registro is None:

            return

        fecha = registro.get(
            "fechaHora",
            ""
        )

        if not fecha:

            return

        carpeta = "registros_5min"

        if not os.path.exists(
            carpeta
        ):

            os.makedirs(
                carpeta
            )

        anio_mes = fecha[:7]

        nombre_archivo = (
            f"{carpeta}/"
            f"historial_{anio_mes}.csv"
        )

        archivo_existe = (
            os.path.exists(
                nombre_archivo
            )
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

            escritor.writerow([

                fecha,

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

        print(
            f"✓ CSV 5 min: {nombre_archivo}"
            f" -> {fecha}"
        )

    except Exception as e:

        print(
            f"⚠ Error guardando CSV: {e}"
        )


# =====================================================
# AGREGAR MEDICIÓN PENDIENTE
# =====================================================

def agregar_medicion_pendiente(
    registro
):

    global mediciones_pendientes

    if registro is None:

        return

    medicion = registro.get(
        "medicion"
    )

    if medicion is None:

        return

    # Evitar duplicados.
    for existente in mediciones_pendientes:

        if existente.get(
            "medicion"
        ) == medicion:

            return

    # Si ya fue utilizada, no vuelve
    # a entrar como pendiente.
    if medicion in entry_ids_utilizados:

        return

    mediciones_pendientes.append(
        registro
    )

    mediciones_pendientes.sort(
        key=lambda x: x["fechaReal"]
    )


# =====================================================
# BUSCAR MEDICIÓN PARA UN INTERVALO
# =====================================================

def buscar_medicion_para_intervalo(
    intervalo_objetivo
):

    candidatos = []

    tolerancia = timedelta(
        minutes=TOLERANCIA_MEDICION_MINUTOS
    )

    limite_inferior = (
        intervalo_objetivo -
        tolerancia
    )

    limite_superior = (
        intervalo_objetivo +
        tolerancia
    )

    for registro in mediciones_pendientes:

        if registro.get(
            "medicion"
        ) in entry_ids_utilizados:

            continue

        fecha_real = registro.get(
            "fechaReal"
        )

        if fecha_real is None:

            continue

        if (
            fecha_real >= limite_inferior
            and fecha_real <= limite_superior
        ):

            diferencia = abs(
                (
                    fecha_real -
                    intervalo_objetivo
                ).total_seconds()
            )

            candidatos.append(
                (
                    diferencia,
                    fecha_real,
                    registro
                )
            )

    if not candidatos:

        return None

    # Ordenar por distancia al objetivo.
    #
    # En caso de empate:
    # se prioriza la medición anterior.
    candidatos.sort(
        key=lambda x: (
            x[0],
            0 if x[1] <= intervalo_objetivo else 1
        )
    )

    mejor = candidatos[0][2]

    return mejor


# =====================================================
# GENERAR REGISTROS DE 5 MINUTOS
# =====================================================

def procesar_intervalos_5_minutos():

    global ultimo_intervalo_generado
    global mediciones_pendientes

    if not mediciones_pendientes:

        return

    # La medición más nueva disponible.
    mediciones_pendientes.sort(
        key=lambda x: x["fechaReal"]
    )

    fecha_mas_nueva = (
        mediciones_pendientes[-1]["fechaReal"]
    )

    # El último intervalo que podemos cerrar
    # es aquel cuya ventana ya terminó.
    #
    # Ejemplo:
    #
    # Objetivo 18:05
    # Ventana hasta 18:07
    #
    # Recién cuando tenemos información hasta
    # 18:07 podemos decidir.
    ultimo_intervalo_posible = (
        fecha_mas_nueva -
        timedelta(
            minutes=TOLERANCIA_MEDICION_MINUTOS
        )
    )

    ultimo_intervalo_posible = (
        obtener_intervalo_5_minutos(
            ultimo_intervalo_posible
        )
    )

    if ultimo_intervalo_generado is None:

        primera_fecha = (
            mediciones_pendientes[0]["fechaReal"]
        )

        primer_intervalo = (
            obtener_intervalo_5_minutos(
                primera_fecha
            )
        )

        ultimo_intervalo_generado = (
            primer_intervalo -
            timedelta(
                minutes=INTERVALO_REGISTRO_MINUTOS
            )
        )

    siguiente_intervalo = (
        ultimo_intervalo_generado +
        timedelta(
            minutes=INTERVALO_REGISTRO_MINUTOS
        )
    )

    while (
        siguiente_intervalo
        <= ultimo_intervalo_posible
    ):

        registro_elegido = (
            buscar_medicion_para_intervalo(
                siguiente_intervalo
            )
        )

        if registro_elegido is not None:

            # La medición real solamente puede
            # utilizarse una vez.
            medicion = registro_elegido[
                "medicion"
            ]

            entry_ids_utilizados.add(
                medicion
            )

            # Crear una copia del registro.
            registro_final = (
                registro_elegido.copy()
            )

            # MUY IMPORTANTE:
            #
            # La fecha del registro final pasa
            # a ser la del intervalo de 5 minutos.
            #
            # Ejemplo:
            #
            # dato real: 18:07
            # intervalo: 18:05
            #
            # CSV:
            # 18:05
            registro_final[
                "fechaHora"
            ] = siguiente_intervalo.strftime(
                "%Y-%m-%d %H:%M:%S"
            )

            registro_final[
                "fechaIntervalo"
            ] = siguiente_intervalo

            # Guardar en historial.
            historial.append(
                registro_final
            )

            # Guardar CSV.
            guardar_en_csv(
                registro_final
            )

            print()
            print(
                "✓ INTERVALO DE 5 MINUTOS"
            )

            print(
                f"  Intervalo: "
                f"{siguiente_intervalo.strftime('%Y-%m-%d %H:%M:%S')}"
            )

            print(
                f"  Medición real: "
                f"{registro_elegido['fechaReal'].strftime('%Y-%m-%d %H:%M:%S')}"
            )

            print(
                f"  Entry ID: "
                f"{registro_elegido['medicion']}"
            )

            print(
                f"  DS18B20: "
                f"{registro_elegido['temperaturaDS']:.2f} °C"
            )

            print(
                f"  DHT22: "
                f"{registro_elegido['temperaturaDHT']:.2f} °C"
            )

            print(
                f"  Humedad: "
                f"{registro_elegido['humedad']:.2f} %"
            )

            # Eliminar la medición utilizada
            # de las pendientes.
            mediciones_pendientes = [

                registro
                for registro
                in mediciones_pendientes

                if registro.get(
                    "medicion"
                ) != medicion

            ]

        else:

            # No encontramos ninguna medición
            # dentro de la tolerancia.
            #
            # En este caso NO inventamos un dato.
            #
            # Dejamos el intervalo sin generar
            # y avanzamos.
            print()
            print(
                "⚠ Sin medición válida para intervalo:"
            )

            print(
                f"  {siguiente_intervalo.strftime('%Y-%m-%d %H:%M:%S')}"
            )

        ultimo_intervalo_generado = (
            siguiente_intervalo
        )

        siguiente_intervalo = (
            siguiente_intervalo +
            timedelta(
                minutes=INTERVALO_REGISTRO_MINUTOS
            )
        )

    # Mantener solamente los últimos 1000
    # registros procesados en memoria.
    #
    # Esto NO afecta los CSV.
    if len(historial) > 1000:

        del historial[:-1000]


# =====================================================
# CARGAR HISTORIAL INICIAL DE THINGSPEAK
# =====================================================

def cargar_historial_inicial():

    global ultimo_entry_id_procesado

    print()
    print(
        "========================================"
    )

    print(
        " CARGANDO HISTORIAL DE THINGSPEAK"
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

            "results":
                8000

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
                "⚠ No hay registros históricos."
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

        registros_validos = []

        for feed in feeds:

            registro = (
                procesar_registro_thingspeak(
                    feed
                )
            )

            if registro is not None:

                registros_validos.append(
                    registro
                )

        registros_validos.sort(
            key=lambda x: x["fechaReal"]
        )

        if not registros_validos:

            print(
                "⚠ No hay registros válidos."
            )

            return

        # El último dato real recibido
        # se utiliza para /datos.
        ultimo_registro = (
            registros_validos[-1]
        )

        datos_actuales[1] = (
            ultimo_registro.copy()
        )

        datos_actuales[1][
            "conectado"
        ] = False

        # =================================================
        # DETERMINAR CONEXIÓN
        # =================================================

        ahora_utc = datetime.now(
            timezone.utc
        )

        fecha_ultimo_dato = (
            obtener_datetime_thingspeak(
                feeds[-1].get(
                    "created_at",
                    ""
                )
            )
        )

        if fecha_ultimo_dato is not None:

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

                print(
                    "⚠ Nodo 1: DESCONECTADO"
                )

        # =================================================
        # AGREGAR MEDICIONES PENDIENTES
        # =================================================

        for registro in registros_validos:

            agregar_medicion_pendiente(
                registro
            )

        # =================================================
        # ESTABLECER ENTRY ID
        # =================================================

        ultimo_entry_id_procesado = (
            ultimo_registro["medicion"]
        )

        # =================================================
        # GENERAR HISTORIAL DE 5 MINUTOS
        # =================================================

        procesar_intervalos_5_minutos()

        print()
        print(
            f"✓ Mediciones reales válidas: "
            f"{len(registros_validos)}"
        )

        print(
            f"✓ Registros de 5 minutos generados: "
            f"{len(historial)}"
        )

        print(
            f"✓ Mediciones pendientes: "
            f"{len(mediciones_pendientes)}"
        )

        print(
            f"✓ Último Entry ID: "
            f"{ultimo_entry_id_procesado}"
        )

        print(
            "========================================"
        )

    except requests.exceptions.RequestException as e:

        print(
            f"⚠ Error cargando ThingSpeak: {e}"
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
                f"⚠ Error monitorizando conexión: {e}"
            )

            time.sleep(10)


# =====================================================
# CONSULTAR THINGSPEAK
# =====================================================

def consultar_thingspeak():

    global ultimo_entry_id_procesado

    print()
    print(
        "========================================"
    )

    print(
        " LECTOR THINGSPEAK - NODO 1"
    )

    print(
        "========================================"
    )

    print(
        f"Canal: {THINGSPEAK_CHANNEL_ID}"
    )

    print(
        f"Consulta cada: "
        f"{INTERVALO_THINGSPEAK} segundos"
    )

    print(
        f"Registro final cada: "
        f"{INTERVALO_REGISTRO_MINUTOS} minutos"
    )

    print(
        f"Tolerancia: "
        f"±{TOLERANCIA_MEDICION_MINUTOS} minutos"
    )

    print(
        f"Desconexión después de: "
        f"{TIEMPO_DESCONEXION // 60} minutos"
    )

    print(
        "========================================"
    )

    while True:

        try:

            url = (
                "https://api.thingspeak.com/"
                f"channels/"
                f"{THINGSPEAK_CHANNEL_ID}/"
                "feeds.json"
            )

            # Pedimos varias mediciones para evitar
            # perder datos si por alguna razón
            # Python tarda más en consultar.
            parametros = {

                "results":
                    100

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
                    "⚠ ThingSpeak sin registros."
                )

                time.sleep(
                    INTERVALO_THINGSPEAK
                )

                continue

            feeds_validos = []

            for feed in feeds:

                try:

                    entry_id = int(
                        feed.get(
                            "entry_id",
                            0
                        )
                    )

                except Exception:

                    continue

                if (
                    ultimo_entry_id_procesado
                    is not None
                    and entry_id
                    <= ultimo_entry_id_procesado
                ):

                    continue

                feeds_validos.append(
                    feed
                )

            feeds_validos.sort(
                key=lambda x: int(
                    x.get(
                        "entry_id",
                        0
                    )
                )
            )

            if not feeds_validos:

                print(
                    f"ThingSpeak: sin datos nuevos."
                )

                time.sleep(
                    INTERVALO_THINGSPEAK
                )

                continue

            # =================================================
            # PROCESAR NUEVAS MEDICIONES
            # =================================================

            for feed in feeds_validos:

                registro = (
                    procesar_registro_thingspeak(
                        feed
                    )
                )

                if registro is None:

                    continue

                datos_actuales[1] = (
                    registro.copy()
                )

                datos_actuales[1][
                    "conectado"
                ] = True

                ultima_recepcion_nodo[1] = (
                    time.time()
                )

                # Agregar a las mediciones reales
                # pendientes.
                agregar_medicion_pendiente(
                    registro
                )

                ultimo_entry_id_procesado = (
                    registro["medicion"]
                )

                print()
                print(
                    "✓ NUEVA MEDICIÓN REAL"
                )

                print(
                    f"  Entry ID: "
                    f"{registro['medicion']}"
                )

                print(
                    f"  Fecha real: "
                    f"{registro['fechaReal'].strftime('%Y-%m-%d %H:%M:%S')}"
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

                print(
                    f"  Punto de rocío: "
                    f"{registro['puntoRocio']:.2f} °C"
                )

                print(
                    f"  Estado: "
                    f"{registro['estado']}"
                )

            # =================================================
            # PROCESAR INTERVALOS DE 5 MINUTOS
            # =================================================

            procesar_intervalos_5_minutos()

            time.sleep(
                INTERVALO_THINGSPEAK
            )

        except requests.exceptions.RequestException as e:

            print(
                f"⚠ Error HTTP consultando ThingSpeak: {e}"
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
    # TOMAR SOLAMENTE LAS ÚLTIMAS 12 HORAS
    # =================================================

    ahora = datetime.now()

    limite = (
        ahora -
        timedelta(
            hours=HORAS_GRAFICO
        )
    )

    historial_grafico = []

    for registro in historial:

        try:

            fecha_texto = registro.get(
                "fechaHora",
                ""
            )

            fecha_registro = (
                datetime.strptime(
                    fecha_texto,
                    "%Y-%m-%d %H:%M:%S"
                )
            )

            if fecha_registro >= limite:

                historial_grafico.append(
                    registro
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

    carpeta = "registros_5min"

    if not os.path.exists(
        carpeta
    ):

        return jsonify([])

    archivos = sorted(
        os.listdir(carpeta),
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
        "registros_5min",
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
        "registros_5min",
        exist_ok=True
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

    print()
    print(
        "========================================"
    )

    print(
        " SERVIDOR WEB - MONITOREO HELADAS"
    )

    print(
        "========================================"
    )

    print()
    print(
        " -> Fuente: ThingSpeak"
    )

    print(
        f" -> Canal: {THINGSPEAK_CHANNEL_ID}"
    )

    print(
        " -> Nodo activo: Nodo 1"
    )

    print(
        " -> Transmisión del nodo: cada 2 minutos"
    )

    print(
        " -> Consulta ThingSpeak: cada 20 segundos"
    )

    print(
        " -> Registros CSV: cada 5 minutos"
    )

    print(
        " -> Gráfico: cada 5 minutos"
    )

    print(
        f" -> Gráfico: últimas {HORAS_GRAFICO} horas"
    )

    print(
        f" -> Tolerancia: "
        f"±{TOLERANCIA_MEDICION_MINUTOS} minutos"
    )

    print(
        f" -> Desconexión: "
        f"{TIEMPO_DESCONEXION // 60} minutos"
    )

    print(
        " -> CSV: separado por punto y coma (;)"
    )

    print(
        " -> CSV: números con coma decimal"
    )

    print(
        " -> CSV: carpeta registros_5min"
    )

    print(
        " -> Codificación: UTF-8-SIG"
    )

    print(
        " -> Flask escuchando en puerto:",
        port
    )

    print(
        "========================================"
    )

    print()

    app.run(
        host="0.0.0.0",
        port=port
    )
