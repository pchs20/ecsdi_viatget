
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

from ecsdi_viatget.utils.FlaskServer import shutdown_server
from ecsdi_viatget.utils.ACLMessages import build_message, send_message, get_message_properties
from ecsdi_viatget.utils.Agent import Agent
from ecsdi_viatget.utils.Logging import config_logger
from ecsdi_viatget.utils.Util import gethostname, registrar_agent, aconseguir_agent

from ecsdi_viatget.ontologies.ACL import ACL
from ecsdi_viatget.ontologies.Viatget import PANT


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
    port = 9003
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
app = Flask(__name__, template_folder='../templates')
if not args.verbose:
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.ERROR)

# Configuration constants and variables
agn = Namespace("http://www.agentes.org#")

# Contador de mensajes
mss_cnt = 0


# Datos del Agente
GestorPagaments = Agent('GestorPagaments',
                  agn.GestorPagaments,
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

    logger.info("Ens registrem")
    global mss_cnt

    gr = registrar_agent(GestorPagaments, DirectoryAgent, agn.GestorPagaments, mss_cnt)

    mss_cnt +=1

    return gr

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
    """
    Entrypoint de comunicacion
    """
    global dsgraph
    global mss_cnt
    pass

    logger.info("Peticio fer pagament rebuda")

    message = request.args['content']
    gm = Graph()
    gm.parse(data=message,format='xml')
    msg = get_message_properties(gm)

    if msg is None:
        gr = build_message(Graph(), ACL['not-understood'], sender=GestorPagaments.uri, msgcnt=mss_cnt)
    else:
        perf = msg['performative']

        if perf != ACL.request:
            gr = build_message(Graph(), ACL['not-understood'], sender=GestorPagaments.uri, msgcnt=mss_cnt)
        else:
            if 'content' in msg:
                content = msg['content']
                accio = gm.value(subject=content, predicate=RDF.type)

                if accio == PANT.RealitzarPagament:

                    num_targeta = float(gm.value(subject=content,predicate=PANT.numeroTargeta))
                    tipus_targeta = str(gm.value(subject=content,predicate=PANT.tipusTargeta))
                    preu = float(gm.value(subject=content,predicate=PANT.preu))


                    factura = getFacturaPagament(num_targeta,tipus_targeta,preu)
                    gr = build_message(factura,
                                       ACL['inform'],
                                       sender=GestorPagaments.uri,
                                       msgcnt=mss_cnt,
                                       receiver=msg['sender'])

                else:
                    gr = build_message(Graph(), ACL['not-understood'], sender=GestorPagaments.uri, msgcnt=mss_cnt)

    mss_cnt += 1

    logger.info('Petició de pagament resposta')

    return gr.serialize(format='xml')




def getFacturaPagament(numTargeta,tipusTargeta,preu):

    agent_Banc = Agent('', '', '', None)
    aconseguir_agent(
        emisor=GestorPagaments,
        agent=agent_Banc,
        directori=DirectoryAgent,
        tipus=agn.Banc,
        mss_cnt=mss_cnt
    )
    logger.info(agent_Banc)
    graf = Graph()
    graf.bind('PANT', PANT)
    content = URIRef('https://peticio_pagar.org')
    graf.add((content, RDF.type, PANT.Pagar))
    graf.add((content, PANT.preu, Literal(preu)))
    graf.add((content, PANT.numeroTargeta, Literal(numTargeta)))
    graf.add((content, PANT.tipusTargeta, Literal(tipusTargeta)))

    missatge = build_message(
        graf,
        perf=ACL.request,
        sender=GestorPagaments.uri,
        receiver=agent_Banc.uri,
        content=content,
        msgcnt=mss_cnt
    )
    gr = send_message(missatge, agent_Banc.address)
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

