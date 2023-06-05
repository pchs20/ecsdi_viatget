"""
Actor extern Banc
"""

from multiprocessing import Process, Queue
import logging
import argparse
import socket
import random

from flask import Flask, request
from rdflib import Graph, Namespace, Literal, URIRef
from rdflib.namespace import RDF
from datetime import date

from utils.FlaskServer import shutdown_server
from utils.ACLMessages import build_message, get_message_properties
from utils.Agent import Agent
from utils.Logging import config_logger
from utils.Util import gethostname, registrar_agent

from ontologies.ACL import ACL
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
    port = 9041
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
Banc = Agent('Banc',
                  agn.Banc,
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

# Amadeus


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

    gr = registrar_agent(Banc, DirectoryAgent, agn.Banc, mss_cnt)

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

    logger.info('Petició per obtenir factura banc')

    # Extraemos el mensaje y creamos un grafo con el
    message = request.args['content']
    gm = Graph()
    gm.parse(data=message, format="xml")
    msg = get_message_properties(gm)

    # Comprobamos que sea un mensaje FIPA ACL
    if msg is None:
        # Si no es, respondemos que no hemos entendido el mensaje
        gr = build_message(Graph(), ACL['not-understood'], sender=Banc.uri, msgcnt=mss_cnt)
    else:
        # Obtenemos la performativa
        perf = msg['performative']

        if perf != ACL.request:
            # Si no es un request, respondemos que no hemos entendido el mensaje
            gr = build_message(Graph(), ACL['not-understood'], sender=Banc.uri, msgcnt=mss_cnt)
        else:
            # Averiguamos el tipo de la accion
            if 'content' in msg:
                content = msg['content']
                accio = gm.value(subject=content, predicate=RDF.type)

                # PROCÉS DE TRACTAMENT DE LA REQUEST

                if accio == PANT.Pagar:
                    preu = float(gm.value(subject=content, predicate=PANT.preu))

                    validacio = crearValidacio(preu)
                    gr = build_message(validacio,
                                       ACL['inform'],
                                       sender=Banc.uri,
                                       msgcnt=mss_cnt,
                                       receiver=msg['sender'])

                else:
                    # Si no és una petició d'allotjaments
                    gr = build_message(Graph(), ACL['not-understood'], sender=Banc.uri,
                                       msgcnt=mss_cnt)
    mss_cnt += 1

    logger.info('Petició pagar resposta')

    return gr.serialize(format='xml')


def crearValidacio(preu):
    data_avui = date.today().strftime('%d/%m/%Y')

    graf = Graph()
    graf.bind('PANT', PANT)
    content = URIRef('https://validacio_pagament.org')
    graf.add((content, RDF.type, PANT.ValidacioPagament))
    graf.add((content, PANT.preu, Literal(preu)))
    graf.add((content, PANT.data, Literal(data_avui)))

    return graf

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
