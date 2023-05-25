# -*- coding: utf-8 -*-
"""
Agent recol·lector de possibilitats d'allotjament
"""

from multiprocessing import Process, Queue
import logging
import argparse
import socket

from flask import Flask, request, render_template
from rdflib import Graph, Namespace, Literal, URIRef
from rdflib.namespace import RDF

from utils.FlaskServer import shutdown_server
from utils.ACLMessages import build_message, send_message, get_message_properties
from utils.Agent import Agent
from utils.Logging import config_logger
from utils.Util import gethostname, registrar_agent, aconseguir_agent
from utils.ExcepcioGeneracioViatge import ExcepcioGeneracioViatge

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
    port = 9001
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
AssistentVirtual = Agent('AssistentVirtual',
                  agn.AssistentVirtual,
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

    gr = registrar_agent(AssistentVirtual, DirectoryAgent, agn.AssistentVirtual, mss_cnt)

    mss_cnt +=1

    return gr


def demanar_planificacio(ciutatIni, ciutatFi, dataIni, dataFi, pressupost, centric,
                                    ludica, festiva, cultural, mati, tarda, nit):
    # Obtenir el gestor de paquets
    gestorPaquets = Agent(None, None, None, None)
    aconseguir_agent(
        emisor=AssistentVirtual,
        agent=gestorPaquets,
        directori=DirectoryAgent,
        tipus=agn.GestorPaquets,
        mss_cnt=mss_cnt
    )

    # Creem el graf amb la petició
    g = Graph()
    peticio = URIRef('https://peticio.org')
    g.bind('PANT', PANT)
    g.add((peticio, RDF.type, PANT.DemanarViatge))

    # Incorporem a la petició les dades rebudes per l'usuari
    ciutatIniObj = URIRef('https://ciutatIni.org')
    g.add((ciutatIniObj, RDF.type, PANT.Ciutat))
    g.add((ciutatIniObj, PANT.nom, Literal(ciutatIni)))
    g.add((peticio, PANT.teComAPuntInici, URIRef(ciutatIniObj)))

    ciutatFiObj = URIRef('https://ciutatFi.org')
    g.add((ciutatFiObj, RDF.type, PANT.Ciutat))
    g.add((ciutatFiObj, PANT.nom, Literal(ciutatFi)))
    g.add((peticio, PANT.teComAPuntFinal, URIRef(ciutatFiObj)))

    g.add((peticio, PANT.dataInici, Literal(dataIni)))
    g.add((peticio, PANT.dataFi, Literal(dataFi)))
    g.add((peticio, PANT.pressupost, Literal(pressupost)))
    g.add((peticio, PANT.activitatsQuantLudiques, Literal(ludica)))
    g.add((peticio, PANT.activitatsQuantCulturals, Literal(cultural)))
    g.add((peticio, PANT.activitatsQuantFestives, Literal(festiva)))

    if mati:
        g.add((peticio, PANT.franja, Literal("mati")))
    if tarda:
        g.add((peticio, PANT.franja, Literal("tarda")))
    if nit:
        g.add((peticio, PANT.franja, Literal("nit")))

    # Construïm, enviem i rebem resposta
    missatge = build_message(
        g,
        perf=ACL.request,
        sender=AssistentVirtual.uri,
        receiver=gestorPaquets.uri,
        content=peticio,
        msgcnt=mss_cnt
    )
    gr = send_message(missatge, gestorPaquets.address)

    missatge = gr.value(predicate=RDF.type, object=ACL.FipaAclMessage)
    paquet = gr.value(subject=missatge, predicate=ACL.content)

    # Dades allotjament
    allotjament_obj = gr.value(subject=paquet, predicate=PANT.teAllotjament)
    allotjament = {}
    allotjament['nom'] = str(gr.value(subject=allotjament_obj, predicate=PANT.nom))
    allotjament['preu'] = float(gr.value(subject=allotjament_obj, predicate=PANT.preu))
    allotjament['centric'] = bool(gr.value(subject=allotjament_obj, predicate=PANT.centric))

    paquet = {'allotjament': allotjament, }

    return paquet


@app.route("/formulari", methods=['GET', 'POST'])
def interaccio_usuari():
    """
        Permite la comunicacion con el agente via un navegador
        via un formulario
        """
    if request.method == 'GET':
        logger.info('Mostrem formulari per demanar paquet')
        return render_template('formulari.html')

    else:   # POST
        ciutatIni = request.form.get('ciutatIni')
        ciutatFi = request.form.get('ciutatFi')
        dataIni = request.form.get('dataIni')
        dataFi = request.form.get('dataFi')
        pressupost = request.form.get('pressupost')
        centric = bool(request.form.get('centric', False))
        ludica = request.form.get('ludica')
        festiva = request.form.get('festiva')
        cultural = request.form.get('cultural')
        mati = bool(request.form.get('mati', False))
        tarda = bool(request.form.get('tarda', False))
        nit = bool(request.form.get('nit', False))

        try:
            paquet = demanar_planificacio(ciutatIni, ciutatFi, dataIni, dataFi, pressupost, centric,
                                    ludica, festiva, cultural, mati, tarda, nit)
            return render_template('resultat.html', paquet=paquet)
        except ExcepcioGeneracioViatge as e:
            return render_template('formulari.html', error=e.motiu)


@app.route("/stop")
def stop():
    """
    Entrypoint que para el agente

    :return:
    """
    tidyup()
    shutdown_server()
    return "Parando Servidor"


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

