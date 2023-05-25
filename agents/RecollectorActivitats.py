# -*- coding: utf-8 -*-
"""
Agent recol·lector de possibilitats d'activitats
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
    port = 9030
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
RecollectorActivitats = Agent('RecollectorActivitats',
                  agn.RecollectorActivitats,
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

# Data de l'últim refresh de les activitats
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

    gr = registrar_agent(RecollectorActivitats, DirectoryAgent, agn.RecollectorActivitats, mss_cnt)

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

    logger.info('Petició de cerca activitats rebuda')

    # Extraemos el mensaje y creamos un grafo con el
    message = request.args['content']
    gm = Graph()
    gm.parse(data=message, format='xml')
    msg = get_message_properties(gm)

    # Comprobamos que sea un mensaje FIPA ACL
    if msg is None:
        # Si no es, respondemos que no hemos entendido el mensaje
        gr = build_message(Graph(), ACL['not-understood'], sender=RecollectorActivitats.uri, msgcnt=mss_cnt)
    else:
        # Obtenemos la performativa
        perf = msg['performative']

        if perf != ACL.request:
            # Si no es un request, respondemos que no hemos entendido el mensaje
            gr = build_message(Graph(), ACL['not-understood'], sender=RecollectorActivitats.uri, msgcnt=mss_cnt)
        else:
            # Averiguamos el tipo de la accion
            if 'content' in msg:
                content = msg['content']
                accio = gm.value(subject=content, predicate=RDF.type)

                # PROCÉS DE TRACTAMENT DE LA REQUEST

                if accio == PANT.ObtenirActivitats:
                    # Agafem la relació amb la ciutat (és una relació) i el nom de la ciutat
                    ciutat_desti = gm.value(subject=content, predicate=PANT.teCiutat)
                    ciutat = str(gm.value(subject=ciutat_desti, predicate=PANT.nom))

                    # Agafem dates d'inici i final (son propietats directament)
                    data_ini = str(gm.value(subject=content, predicate=PANT.dataInici))
                    dataIni = datetime.strptime(data_ini, "%d/%m/%Y")
                    data_fi = str(gm.value(subject=content, predicate=PANT.dataFi))
                    dataFi = datetime.strptime(data_fi, "%d/%m/%Y")

                    # Afaggem les franges en què volem buscar activitats
                    frangesObj = gm.triples((None, PANT.franja, None))
                    franges = []
                    for franja in frangesObj:
                        franges.append(franja[2])

                    # Obtenim les possibilitats i retornem la informació
                    possibilitats = obtenir_possibles_activitats(ciutat, franges, dataIni, dataFi)
                    gr = build_message(possibilitats,
                                       ACL['inform'],
                                       sender=RecollectorActivitats.uri,
                                       msgcnt=mss_cnt,
                                       receiver=msg['sender'])

                else:
                    # Si no és una petició d'activitats
                    gr = build_message(Graph(), ACL['not-understood'], sender=RecollectorActivitats.uri,
                                       msgcnt=mss_cnt)
    mss_cnt += 1

    logger.info('Petició de cerca activitats resposta')

    return gr.serialize(format='xml')


def refresh_activitats():
    logger.info('Fem refresh de les activitats que tenim guardades')

    # Obtenim un actor extern d'activitats
    logger.info('Busquem un actor extern activitats')
    actorActivitats = Agent(None, None, None, None)
    aconseguir_agent(
        emisor=RecollectorActivitats,
        agent=actorActivitats,
        directori=DirectoryAgent,
        tipus=agn.ActorActivitats,
        mss_cnt=mss_cnt
    )

    # Construïm el graf de la petició
    g = Graph()
    peticio = URIRef('https://peticio.org')
    g.add((peticio, RDF.type, PANT.ObtenirActivitats))
    missatge = build_message(
        g,
        perf=ACL.request,
        sender=RecollectorActivitats.uri,
        receiver=actorActivitats.uri,
        content=peticio,
        msgcnt=mss_cnt
    )
    gr = send_message(missatge, actorActivitats.address)

    # Guardem les dades a la "BD"
    logger.info('Actualitzem la BD activitats')
    gr.serialize(destination='../bd/activitats.ttl', format='turtle')

    # Actualitzem la data de l'última actualització
    global ultimRefresh
    ultimRefresh = datetime.today()

def obtenir_possibles_activitats(ciutat, franges, dataIni, dataFi):
    # Mirem si cal fer refresh de les dades: si l'últim refresh fa més d'un dia
    today = datetime.today()
    dif = today - ultimRefresh
    if dif > timedelta(days=1):
        refresh_activitats()

    # Recuperem les dades
    gbd = Graph()
    gbd.bind('PANT', PANT)
    gbd.parse(source='../bd/activitats.ttl', format='turtle')

    # Retornem activitats de la ciutat, disponibles a les franges que volem
    franges_in = ", ".join(['"%s"' % f for f in franges])

    queryObj = prepareQuery("""
            PREFIX pant:<https://ontologia.org#>
            SELECT ?Activitat
            WHERE {
                ?Activitat rdf:type pant:Activitat .
                ?Activitat pant:teCiutat ?ciutat .
                ?ciutat rdf:type pant:Ciutat .
                ?ciutat pant:nom "%s" .
                ?Activitat pant:franja ?franja .
                FILTER(?franja IN (%s))
            }
        """ % (ciutat, franges_in))

    result = gbd.query(queryObj).result

    print(len(result))

    gr = Graph()
    gr.bind('PANT', PANT)

    for activitat in result:
        print(activitat)
        activitatObj = URIRef(activitat[0])
        gr.add((activitatObj, RDF.type, PANT.Activitat))
        gr.add((activitatObj, PANT.nom, gbd.value(subject=activitatObj, predicate=PANT.nom)))
        gr.add((activitatObj, PANT.tipus, gbd.value(subject=activitatObj, predicate=PANT.tipus)))
        gr.add((activitatObj, PANT.franja, gbd.value(subject=activitatObj, predicate=PANT.franja)))

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

    # Poblem la BD d'activitats
    refresh_activitats()

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