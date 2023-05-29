# -*- coding: utf-8 -*-
"""
Agent recol·lector de possibilitats de transport
"""

from multiprocessing import Process, Queue
import logging
import argparse
import socket

from flask import Flask, request
from rdflib import Graph, Namespace, Literal, URIRef
from rdflib.namespace import RDF
from rdflib.plugins.sparql import prepareQuery

from utils.FlaskServer import shutdown_server
from utils.ACLMessages import build_message, send_message, get_message_properties
from utils.Agent import Agent
from utils.Logging import config_logger
from utils.Util import gethostname, registrar_agent, aconseguir_agent

from ontologies.ACL import ACL
from ontologies.Viatget import PANT
from datetime import datetime, timedelta


# Paràmetres de la línia de comandes
parser = argparse.ArgumentParser()
parser.add_argument('--open', help="Define si el servidor esta abierto al exterior o no", action='store_true',
                    default=False)
parser.add_argument('--verbose', help="Genera un log de la comunicacion del servidor web", action='store_true',
                        default=False)
parser.add_argument('--port', type=int, help="Puerto de comunicacion del agente")
parser.add_argument('--dhost', help="Host del agente de directorio")
parser.add_argument('--dport', type=int, help="Puerto de comunicacion del agente de directorio")

# Logging
logger = config_logger(level=1)

# parsing de los parametros de la linea de comandos
args = parser.parse_args()

# Configuration stuff
if args.port is None:
    port = 9020
else:
    port = args.port

if args.open:
    hostname = '0.0.0.0'
    hostaddr = gethostname()
else:
    hostaddr = hostname = socket.gethostname()

print('DS Hostname =', hostaddr)

if args.dport is None:
    dport = 9000
else:
    dport = args.dport

if args.dhost is None:
    dhostname = socket.gethostname()
else:
    dhostname = args.dhost

# Flask stuff
app = Flask(__name__)
if not args.verbose:
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.ERROR)

# Configuration constants and variables
agn = Namespace("http://www.agentes.org#")

# Contador de mensajes
mss_cnt = 0

# Datos del Agente
RecollectorTransports = Agent('RecollectorTransports',
                  agn.RecollectorTransports,
                  'http://%s:%d/comm' % (hostaddr, port),
                  'http://%s:%d/Stop' % (hostaddr, port))

# Directory agent address
DirectoryAgent = Agent('DirectoryAgent',
                       agn.Directory,
                       'http://%s:%d/Register' % (dhostname, dport),
                       'http://%s:%d/Stop' % (dhostname, dport))

# Global dsgraph triplestore
dsgraph = Graph()
dsgraph.bind('acl', ACL)
dsgraph.bind('pant', PANT)

# Cola de comunicacion entre procesos
cola1 = Queue()

# Data de l'últim refresh dels allotjaments
ultimRefresh = datetime.today()


def register_message():
    """
    Envia un mensaje de registro al servicio de registro
    usando una performativa Request y una accion Register del
    servicio de directorio

    :param gmess:
    :return:
    """

    logger.info('Nos registramos')

    global mss_cnt

    gr = registrar_agent(RecollectorTransports, DirectoryAgent, agn.RecollectorTransports, mss_cnt)

    mss_cnt += 1

    return gr


@app.route("/iface", methods=['GET', 'POST'])
def browser_iface():
    """
    Permite la comunicacion con el agente via un navegador
    via un formulario
    """
    return 'Nothing to see here'


@app.route("/stop")
def stop():
    """
    Entrypoint que para el agente

    :return:
    """
    tidyup()
    shutdown_server()
    return "Parando Servidor"


@app.route("/comm")
def comunicacion():
    global dsgraph
    global mss_cnt

    logger.info('Petició de cerca transports rebuda')

    # Extraemos el mensaje y creamos un grafo con el
    message = request.args['content']
    gm = Graph()
    gm.parse(data=message, format='xml')
    msg = get_message_properties(gm)

    # Comprobamos que sea un mensaje FIPA ACL
    if msg is None:
        # Si no es, respondemos que no hemos entendido el mensaje
        gr = build_message(Graph(), ACL['not-understood'], sender=RecollectorTransports.uri, msgcnt=mss_cnt)
    else:
        # Obtenemos la performativa
        perf = msg['performative']

        if perf != ACL.request:
            # Si no es un request, respondemos que no hemos entendido el mensaje
            gr = build_message(Graph(), ACL['not-understood'], sender=RecollectorTransports.uri, msgcnt=mss_cnt)
        else:
            # Averiguamos el tipo de la accion
            if 'content' in msg:
                content = msg['content']
                accio = gm.value(subject=content, predicate=RDF.type)

                # PROCÉS DE TRACTAMENT DE LA REQUEST

                if accio == PANT.ObtenirTransports:
                    # Agafem la relació amb la companyia (és una relació) i el nom de la companyia
                    #companyia_transport = gm.value(subject=content, predicate=PANT.deLaCompanyia)
                    #companyia = str(gm.value(subject=companyia_transport, predicate=PANT.nom))

                    # Agafem dates d'inici i final (son propietats directament)
                    #data_ini = str(gm.value(subject=content, predicate=PANT.dataInici))
                    #data_fi = str(gm.value(subject=content, predicate=PANT.dataFi))

                    # Afagem el preu màxim i si l'allotjament ha de ser o no cèntric
                    preuMax = float(gm.value(subject=content, predicate=PANT.preuMaxim))
                    #centric = bool(gm.value(subject=content, predicate=PANT.centric))

                    # Obtenim les possibilitats i retornem la informació
                    possibilitats = obtenir_possibles_transports(preuMax)
                    gr = build_message(possibilitats,
                                       ACL['inform'],
                                       sender=RecollectorTransports.uri,
                                       msgcnt=mss_cnt,
                                       receiver=msg['sender'])

                else:
                    # Si no és una petició de transports
                    gr = build_message(Graph(), ACL['not-understood'], sender=RecollectorTransports.uri,
                                       msgcnt=mss_cnt)
    mss_cnt += 1

    logger.info('Petició de cerca transports resposta')

    return gr.serialize(format='xml')


def refresh_transports():
    logger.info('Fem refresh dels transports que tenim guardats')

    # Obtenim un actor extern de transports
    logger.info('Busquem un actor extern transports')
    actorTransports = Agent(None, None, None, None)
    aconseguir_agent(
        emisor=RecollectorTransports,
        agent=actorTransports,
        directori=DirectoryAgent,
        tipus=agn.ActorTransports,
        mss_cnt=mss_cnt
    )

    # Construïm el graf de la petició
    g = Graph()
    peticio = URIRef('https://peticio.org')
    g.add((peticio, RDF.type, PANT.ObtenirTransports))
    missatge = build_message(
        g,
        perf=ACL.request,
        sender=RecollectorTransports.uri,
        receiver=actorTransports.uri,
        content=peticio,
        msgcnt=mss_cnt
    )
    gr = send_message(missatge, actorTransports.address)

    # Guardem les dades a la "BD"
    logger.info('Actualitzem la BD transports')
    gr.serialize(destination='../bd/transports.ttl', format='turtle')

    # Actualitzem la data de l'última actualització
    global ultimRefresh
    ultimRefresh = datetime.today()


def obtenir_possibles_transports(preuMax):
    # Mirem si cal fer refresh de les dades: si l'últim refresh fa més d'un dia
    today = datetime.today()
    dif = today - ultimRefresh
    if dif > timedelta(days=1):
        refresh_transports()

    # Recuperem les dades
    gbd = Graph()
    gbd.bind('PANT', PANT)
    gbd.parse(source='../bd/transports.ttl', format='turtle')

    # ToDo: Fer consulta en funció dels paràmetres rebuts a la funció i acabar retornant el resultat
    query = prepareQuery("""
        PREFIX pant:<https://ontologia.org#>
        SELECT ?Transport
        WHERE {
            ?Transport rdf:type pant:Transport .
            ?Transport pant:preu ?preu .
            FILTER(?preu <= %s)
        }
        ORDER BY ?preu
        LIMIT 5
    """ % (preuMax ))

    resultados = gbd.query(query).result
    num_resultados = len(resultados)
    gr = Graph()
    gr.bind('PANT', PANT)

    for a in resultados:
        aObj = URIRef(a[0])
        gr.add((aObj, RDF.type, PANT.Transport))
        gr.add((aObj, PANT.tipus, gbd.value(subject=aObj, predicate=PANT.tipus)))
        gr.add((aObj, PANT.deLaCompanyia, gbd.value(subject=aObj, predicate=PANT.deLaCompanyia)))
        gr.add((aObj, PANT.preu, gbd.value(subject=aObj, predicate=PANT.preu)))

    for resultado in resultados:
        enlace = resultado[0]
        if isinstance(enlace, URIRef):
            # Obtener el enlace como cadena de texto
            enlace_str = str(enlace)

            # Obtener el nombre del recurso (Allotjament)
            transport = enlace_str.split('/')[-1]

            # Obtener otros datos del recurso utilizando SPARQL
            query_datos = prepareQuery("""
                       PREFIX pant:<https://ontologia.org#>
                       SELECT ?tipus ?companyia ?preu
                       WHERE {
                           <%s> pant:tipus ?tipus ;
                               pant:preu ?preu ;
                               pant:deLaCompanyia ?companyia .
                       }
                   """ % enlace_str)

            resultados_datos = gbd.query(query_datos)

            for resultado_datos in resultados_datos:
                tipus = str(resultado_datos['tipus'])
                preu = float(resultado_datos['preu'])


    return gr


def tidyup():
    """
    Acciones previas a parar el agente

    """
    global cola1
    cola1.put(0)


def agentbehavior1():
    """
    Un comportamiento del agente

    :return:
    """

    # Poblem la BD d'allotjaments
    refresh_transports()

    # Registramos el agente
    register_message()


if __name__ == '__main__':
    # Ponemos en marcha los behaviors
    ab1 = Process(target=agentbehavior1)
    ab1.start()

    # Ponemos en marcha el servidor
    app.run(host=hostname, port=port)

    # Esperamos a que acaben los behaviors
    ab1.join()
    logger.info('The End')
