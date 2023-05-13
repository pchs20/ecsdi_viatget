# -*- coding: utf-8 -*-
"""
Agent recol·lector de possibilitats d'allotjament
"""

from multiprocessing import Process, Queue
import logging
import argparse
import socket

from flask import Flask, request
from rdflib import Graph, Namespace, Literal, URIRef
from rdflib.namespace import RDF

from utils.FlaskServer import shutdown_server
from utils.ACLMessages import build_message, send_message, get_message_properties
from utils.Agent import Agent
from utils.Logging import config_logger
from utils.Util import gethostname, registrar_agent, aconseguir_agent

from utils.OntoNamespaces import ACL, DSO
from ontologies.Viatget import PANT


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
    port = 9010
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
RecollectorAllotjaments = Agent('RecollectorAllotjaments',
                  agn.RecollectorAllotjaments,
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

    gr = registrar_agent(RecollectorAllotjaments, DirectoryAgent, PANT.AgentAllotjament, mss_cnt)

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

    logger.info('Petició de cerca allotjaments rebuda')

    # Extraemos el mensaje y creamos un grafo con el
    """message = request.args['content']
    gm = Graph()
    gm.parse(data=message)"""

    # ToDo: Deshardcodejar
    gm = Graph()
    gm.bind('PANT', PANT)
    peticio = URIRef('https://peticioooo.org')
    gm.add((peticio, RDF.type, PANT.ObtenirAllotjaments))

    ciutat = URIRef('https://ciutatatatatat.org')
    gm.add((ciutat, RDF.type, PANT.Ciutat))
    gm.add((ciutat, PANT.nom, Literal('Barcelona')))
    gm.add((peticio, PANT.teCiutat, URIRef(ciutat)))
    gm.add((peticio, PANT.dataInici, Literal('20-02-20')))
    gm.add((peticio, PANT.dataFi, Literal('20-02-20')))
    gm.add((peticio, PANT.preuMaxim, Literal(500)))
    gm.add((peticio, PANT.esCentric, Literal(True)))
    gmsg = build_message(gm, perf=ACL.request, sender=RecollectorAllotjaments.uri,
                        receiver=RecollectorAllotjaments.uri, content=peticio, msgcnt=1)

    #msg = get_message_properties(gm)
    msg = get_message_properties(gmsg)

    # Comprobamos que sea un mensaje FIPA ACL
    if msg is None:
        # Si no es, respondemos que no hemos entendido el mensaje
        gr = build_message(Graph(), ACL['not-understood'], sender=RecollectorAllotjaments.uri, msgcnt=mss_cnt)
    else:
        # Obtenemos la performativa
        perf = msg['performative']

        if perf != ACL.request:
            # Si no es un request, respondemos que no hemos entendido el mensaje
            gr = build_message(Graph(), ACL['not-understood'], sender=RecollectorAllotjaments.uri, msgcnt=mss_cnt)
        else:
            # Averiguamos el tipo de la accion
            if 'content' in msg:
                content = msg['content']
                accio = gm.value(subject=content, predicate=RDF.type)

                # PROCÉS DE TRACTAMENT DE LA REQUEST

                if accio == PANT.ObtenirAllotjaments:
                    # Agafem la relació amb la ciutat (és una relació) i el nom de la ciutat
                    ciutat_desti = gm.value(subject=content, predicate=PANT.teCiutat)
                    ciutat = str(gm.value(subject=ciutat_desti, predicate=PANT.nom))

                    # Agafem dates d'inici i final (son propietats directament)
                    data_ini = str(gm.value(subject=content, predicate=PANT.dataInici))
                    data_fi = str(gm.value(subject=content, predicate=PANT.dataFi))

                    # Afagem el preu màxim i si l'allotjament ha de ser o no cèntric
                    preuMax = float(gm.value(subject=content, predicate=PANT.preuMaxim))
                    esCentric = bool(gm.value(subject=content, predicate=PANT.esCentric))

                    # Obtenim les possibilitats i retornem la informació
                    possibilitats = obtenir_possibles_allotjaments(ciutat, data_ini, data_fi, preuMax, esCentric)
                    gr = build_message(possibilitats,
                                       ACL['inform'],
                                       sender=RecollectorAllotjaments.uri,
                                       msgcnt=mss_cnt,
                                       receiver=msg['sender'])

                else:
                    # Si no és una petició d'allotjaments
                    gr = build_message(Graph(), ACL['not-understood'], sender=RecollectorAllotjaments.uri,
                                       msgcnt=mss_cnt)
    mss_cnt += 1

    logger.info('Petició de cerca allotjaments resposta')

    return gr.serialize(format='xml')


def obtenir_possibles_allotjaments(ciutat, data_ini, data_fi, preuMax, esCentric):
    # ToDo
    logger.info("Busquem un actor extern d'allotjaments")

    # Obtenim un actor extern d'allotjaments
    actorAllotjaments = Agent(None, None, None, None)
    aconseguir_agent(
        emisor=RecollectorAllotjaments,
        agent=actorAllotjaments,
        directori=DirectoryAgent,
        tipus=agn.ActorAllotjaments,
        mss_cnt=mss_cnt
    )

    # Construïm el graf de la petició
    g = Graph()
    peticio = URIRef('https://peticio.org')
    g.add((peticio, RDF.type, PANT.ObtenirAllotjaments))
    missatge = build_message(
        g,
        perf=ACL.request,
        sender=RecollectorAllotjaments.uri,
        receiver=actorAllotjaments.uri,
        content=peticio,
        msgcnt=mss_cnt
    )
    gr = send_message(missatge, actorAllotjaments.address)

    # Guardem les dades en una BD fictícia
    gr.serialize(destination='../bd/allotjaments.ttl', format='turtle')

    # Recuperem les dades
    gbd = Graph()
    gbd.bind('PANT', PANT)
    gbd.parse(source='../bd/allotjaments.ttl', format='turtle')

    # ToDo: Fer consulta en funció dels paràmetres rebuts a la funció
    resultat = gr.query(
        query_object="""
        Select ?Allotjament
        where {
            ?Allotjament PANT:preu "%s" .
        }
        LIMIT 30
    """ % (str(100)), initNs=dict(PANT=PANT))

    return gbd

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
    # Registramos el agente
    gr = register_message()


if __name__ == '__main__':
    # Ponemos en marcha los behaviors
    ab1 = Process(target=agentbehavior1)
    ab1.start()

    # Ponemos en marcha el servidor
    app.run(host=hostname, port=port)

    # Esperamos a que acaben los behaviors
    ab1.join()
    logger.info('The End')
