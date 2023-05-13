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

from ecsdi_viatget.utils.FlaskServer import shutdown_server
from ecsdi_viatget.utils.ACLMessages import build_message, send_message, get_message_properties
from ecsdi_viatget.utils.Agent import Agent
from ecsdi_viatget.utils.Logging import config_logger
from ecsdi_viatget.utils.Util import gethostname, registrar_agent, aconseguir_agent

from ecsdi_viatget.utils.OntoNamespaces import ACL, DSO
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

agent_allotjament = Agent('','','',None)

# Datos del Agente
GestorPaquets = Agent('GestorPaquets',
                  agn.GestorPaquets,
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

    """gr = registrar_agent(GestorPaquets,DirectoryAgent,PANT.AgentGestorPaquets,mss_cnt)"""

    mss_cnt +=1

    """return gr"""

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
    """
    Entrypoint de comunicacion
    """
    global dsgraph
    global mss_cnt
    pass

    logger.info("PETICIO COMENÇAR PAQUET REBUDA")

    message = request.args['content']
    gm = Graph()
    gm.parse(data=message,format='xml')
    msg = get_message_properties(gm)

    if msg is None:
        gr = build_message(Graph(), ACL['not-understood'], sender=GestorPaquets.uri, msgcnt=mss_cnt)
    else:
        perf = msg['perfotmative']

        if perf != ACL.request:
            gr = build_message(Graph(), ACL['not-understood'], sender=GestorPaquets.uri, msgcnt=mss_cnt)
        else:
            if 'content' in msg:
                content = msg['content']
                accio = gm.value(subject=content, predicate=RDF.type)

                if accio == PANT.DemanarViatje:

                    # Ciutats destí i inici
                    ciutat_desti = gm.value(subject=content, predicate=PANT.teComAPuntFinal)
                    ciutat_d = str(gm.value(subject=ciutat_desti, predicate=PANT.nom))

                    ciutat_origen = gm.value(subject=content, predicate=PANT.teComAPuntInici)
                    ciutat = str(gm.value(subject=ciutat_origen, predicate=PANT.nom))

                    # Pressupost
                    pressupost = float(gm.value(subject=content, predicate=PANT.pressupost))

                    # Preferencia Allotjament
                    allotjament_centric = bool(gm.value(subject=content, predicate=PANT.allotjamentCentric))

                    # Dates viatje
                    data_ini = str(gm.value(subject=content, predicate=PANT.dataInici))
                    data_fi = str(gm.value(subject=content, predicate=PANT.dataFi))

                    # Retornem info
                    allotjaments = getAllotjaments(data_ini,data_fi,allotjament_centric,ciutat_desti,pressupost)

                    #Operacio calcula millor opcio combinacio transport i allotjament



                    #gr = build_message()



                else:
                    gr = build_message(Graph(), ACL['not-understood'], sender=GestorPaquets.uri, msgcnt=mss_cnt)
def getAllotjaments(dataIni, dataFi, centric, ciutat_desti, preuMax):
    logger.info("DEMANA ALLOTJAMENTS")

    agent_allotjament = Agent('', '', '', None)
    aconseguir_agent(GestorPaquets,agent_allotjament,DirectoryAgent,agn.RecollectorAllotjaments,mss_cnt)
    logger.info(agent_allotjament)

    graf = Graph()
    content = URIRef('https://peticio_allotjaments.org')
    graf.add((content,RDF.type,PANT.ObtenirAllotjaments))
    graf.add((content, PANT.esCentric, Literal(centric)))
    graf.add((content, PANT.deCiutat, Literal(ciutat_desti)))
    graf.add((content, PANT.data_fi, Literal(dataFi)))
    graf.add((content, PANT.data_inici, Literal(dataIni)))
    graf.add((content, PANT.preu_maxim, Literal(preuMax)))

    missatge = build_message(graf,GestorPaquets.uri,agent_allotjament.uri,content,mss_cnt)
    gr = send_message(missatge,agent_allotjament.address)


    llista_allotjaments = gr.triples((None, RDF.type, PANT.Allotjament))

    return llista_allotjaments
"""
def getTransport(puntInici, puntFinal, dataIni, dataFi, preuMax):
    logger.info("DEMANA TRANSPORT")

    agent_transport = Agent('', '', '', None)
    aconseguir_agent(GestorPaquets, agent_transport, DirectoryAgent, agn.RecollectorTransport, mss_cnt)
    logger.info(agent_transport)

    graf = Graph()
    content = URIRef("https://transports.org")
    graf.add((content, RDF.type))

    graf.add((content, RDF.type, PANT.ObtenirTransport))
    graf.add((content, PANT.te_com_a_punt_final, Literal(puntFinal)))

    agent_transport = get_info_agent(agn.RecollectorTransport, DirectoryAgent, GestorPaquets, get_count())

    resposta = send_message(
        build_message(graf, perf=ACL.request, content=content, receiver=agent_transport.uri, sender=GestorPaquets.uri,
                      msgcnt=get_count()), agent_transport.address)

    llista_transport = resposta.triples((None, RDF.type, PANT.Transport))
"""
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

