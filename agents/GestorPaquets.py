# -*- coding: utf-8 -*-
"""
Agent recol·lector de possibilitats d'allotjament
"""
import math
from datetime import datetime, timedelta
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
    port = 9002
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

    gr = registrar_agent(GestorPaquets, DirectoryAgent, agn.GestorPaquets, mss_cnt)

    mss_cnt +=1

    return gr


def generar_paquet(ciutatIni, ciutatFi, dataIni, dataFi, pressupost,
                   ludica, festiva, cultural, centric, franges):

    # PLANIFICACIÓ ALLOTJAMENT I TRANSPORTS

    resposta_allotjaments = getPossiblesAllotjaments(dataIni, dataFi, centric, ciutatFi, pressupost)
    possibles_transport1 = getPossiblesTransports(pressupost)
    possibles_transport2 = getPossiblesTransports(pressupost)

    # Aquí faríem la planificació allotjament + transport
    llista_allotjaments = resposta_allotjaments.triples((None, RDF.type, PANT.Allotjament))
    allotjament_obj = next(llista_allotjaments)[0]
    llista_transports1 = possibles_transport1.triples((None, RDF.type, PANT.Transport))
    transport1 = next(llista_transports1)[0]
    llista_transports2 = possibles_transport2.triples((None, RDF.type, PANT.Transport))
    transport2 = next(llista_transports2)[0]

    graf = Graph()
    paquet = URIRef('https://paquetTancat.org')
    graf.add((paquet, RDF.type, PANT.Paquet))

    # Posem dades decidides de l'allotjament
    graf.add((allotjament_obj, PANT.nom, resposta_allotjaments.value(subject=allotjament_obj, predicate=PANT.nom)))
    graf.add((allotjament_obj, PANT.preu, resposta_allotjaments.value(subject=allotjament_obj, predicate=PANT.preu)))
    graf.add((allotjament_obj, PANT.centric, resposta_allotjaments.value(subject=allotjament_obj, predicate=PANT.centric)))
    graf.add((paquet, PANT.teAllotjament, URIRef(allotjament_obj)))

    # Posem dades decidides del vol d'anada
    graf.add((transport1, PANT.tipus, possibles_transport1.value(subject=transport1, predicate=PANT.tipus)))
    graf.add((transport1, PANT.deLaCompanyia, possibles_transport1.value(subject=transport1, predicate=PANT.deLaCompanyia)))
    graf.add((transport1, PANT.preu, possibles_transport1.value(subject=transport1, predicate=PANT.preu)))
    graf.add((paquet, PANT.teTransportAnada, URIRef(transport1)))

    # Posem dades decidides del vol de tornada
    graf.add((transport2, PANT.tipus, possibles_transport2.value(subject=transport2, predicate=PANT.tipus)))
    graf.add((transport2, PANT.deLaCompanyia, possibles_transport2.value(subject=transport2, predicate=PANT.deLaCompanyia)))
    graf.add((transport2, PANT.preu, possibles_transport2.value(subject=transport2, predicate=PANT.preu)))
    graf.add((paquet, PANT.teTransportTornada, URIRef(transport2)))


    # PLANIFICACIÓ ACTIVITATS
    resposta_activitats = getPossiblesActivitats(ciutatFi, dataIni, dataFi, franges)
    llista_activitats = []
    for s, p, o in resposta_activitats.triples((None, RDF.type, PANT.Activitat)):
        llista_activitats.append(s)

    dataIni_date = datetime.strptime(dataIni, "%d/%m/%Y")
    dataFi_date = datetime.strptime(dataFi, "%d/%m/%Y")
    numDies = (dataFi_date - dataIni_date).days - 1
    estadistiquesFranja = calcularEstadistiquesFranja(ludica, festiva, cultural, numDies)

    nAct = 0
    for franja in franges:
        i = 0
        data_act = dataIni_date + timedelta(days=1)
        estadistiques_act = estadistiquesFranja.copy()
        while data_act < dataFi_date:
            if i == len(llista_activitats):
                i = 0
            act = llista_activitats[i]
            franja_act = str(resposta_activitats.value(subject=act, predicate=PANT.franja))
            if franja_act == franja:
                tipus_act = str(resposta_activitats.value(subject=act, predicate=PANT.tipus))
                if estadistiques_act[tipus_act] > 0:
                    estadistiques_act[tipus_act] -= 1
                    nom_act = str(resposta_activitats.value(subject=act, predicate=PANT.nom))
                    novaActivitat = URIRef('activitat' + str(nAct))
                    graf.add((novaActivitat, RDF.type, PANT.Activitat))
                    graf.add((novaActivitat, PANT.nom, Literal(nom_act)))
                    graf.add((novaActivitat, PANT.tipus, Literal(tipus_act)))
                    graf.add((novaActivitat, PANT.franja, Literal(franja_act)))
                    graf.add((novaActivitat, PANT.data, Literal(data_act.strftime("%d/%m/%Y"))))
                    data_act += timedelta(days=1)
                    nAct += 1
            i += 1

    # CALCULAR EL PREU FINAL DEL PAQUET
    graf.add((paquet, PANT.preu, Literal(100)))

    return graf


# Calculem, aproximadament, quantes activitats de cada tipus per franja hi hauria d'haver
def calcularEstadistiquesFranja(ludica, festiva, cultural, numDies):
    total = ludica + festiva + cultural
    if total == 0:
        ludica = 1
        festiva = 1
        cultural = 1
        total = 3
    estadistiques = {
        'ludica': 0 if ludica == 0 else math.ceil((ludica/total)*numDies),
        'festiva': 0 if festiva == 0 else math.ceil((festiva/total)*numDies),
        'cultural': 0 if cultural == 0 else math.ceil((cultural/total)*numDies)
    }
    return estadistiques


def getPossiblesAllotjaments(dataIni, dataFi, centric, ciutat_desti, preuMax):
    logger.info("DEMANA ALLOTJAMENTS")
    agent_allotjament = Agent('', '', '', None)
    aconseguir_agent(
        emisor=GestorPaquets,
        agent=agent_allotjament,
        directori=DirectoryAgent,
        tipus=agn.RecollectorAllotjaments,
        mss_cnt=mss_cnt
    )
    graf = Graph()
    graf.bind('PANT', PANT)
    content = URIRef('https://peticio_allotjaments.org')
    graf.add((content, RDF.type, PANT.ObtenirAllotjaments))
    graf.add((content, PANT.centric, Literal(centric)))
    ciutat_desti_obj = URIRef('https://ciutatDesti.org')
    graf.add((ciutat_desti_obj, RDF.type, PANT.Ciutat))
    graf.add((ciutat_desti_obj, PANT.nom, Literal(ciutat_desti)))
    graf.add((content, PANT.teCiutat, ciutat_desti_obj))
    graf.add((content, PANT.dataFi, Literal(dataFi)))
    graf.add((content, PANT.dataInici, Literal(dataIni)))
    graf.add((content, PANT.preuMaxim, Literal(preuMax)))

    missatge = build_message(
        graf,
        perf=ACL.request,
        sender=GestorPaquets.uri,
        receiver=agent_allotjament.uri,
        content=content,
        msgcnt=mss_cnt
    )
    gr = send_message(missatge, agent_allotjament.address)
    return gr


def getPossiblesTransports(preuMax):
    logger.info("DEMANA transports")
    agent_transport = Agent('', '', '', None)
    aconseguir_agent(
        emisor=GestorPaquets,
        agent=agent_transport,
        directori=DirectoryAgent,
        tipus=agn.RecollectorTransports,
        mss_cnt=mss_cnt
    )
    graf = Graph()
    graf.bind('PANT', PANT)
    content = URIRef('https://peticio_transports.org')
    graf.add((content, RDF.type, PANT.ObtenirTransports))
    graf.add((content, PANT.preuMaxim, Literal(preuMax)))

    missatge = build_message(
        graf,
        perf=ACL.request,
        sender=GestorPaquets.uri,
        receiver=agent_transport.uri,
        content=content,
        msgcnt=mss_cnt
    )
    gr = send_message(missatge, agent_transport.address)
    return gr


def getPossiblesActivitats(ciutat, dataIni, dataFi, franges):
    logger.info("DEMANA ACTIVITATS")

    agent_activitats = Agent('', '', '', None)
    aconseguir_agent(
        emisor=GestorPaquets,
        agent=agent_activitats,
        directori=DirectoryAgent,
        tipus=agn.RecollectorActivitats,
        mss_cnt=mss_cnt
    )

    graf = Graph()
    graf.bind('PANT', PANT)
    content = URIRef('https://peticio_activitats.org')
    graf.add((content, RDF.type, PANT.ObtenirActivitats))
    ciutat_desti_obj = URIRef('https://ciutatDesti.org')
    graf.add((ciutat_desti_obj, RDF.type, PANT.Ciutat))
    graf.add((ciutat_desti_obj, PANT.nom, Literal(ciutat)))
    graf.add((content, PANT.teCiutat, ciutat_desti_obj))
    graf.add((content, PANT.dataInici, Literal(dataIni)))
    graf.add((content, PANT.dataFi, Literal(dataFi)))
    for franja in franges:
        graf.add((content, PANT.franja, Literal(franja)))

    missatge = build_message(
        graf,
        perf=ACL.request,
        sender=GestorPaquets.uri,
        receiver=agent_activitats.uri,
        content=content,
        msgcnt=mss_cnt
    )
    gr = send_message(missatge, agent_activitats.address)
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

    logger.info("PETICIO COMENÇAR PAQUET REBUDA")

    message = request.args['content']
    gm = Graph()
    gm.parse(data=message,format='xml')
    msg = get_message_properties(gm)

    if msg is None:
        gr = build_message(Graph(), ACL['not-understood'], sender=GestorPaquets.uri, msgcnt=mss_cnt)
    else:
        perf = msg['performative']

        if perf != ACL.request:
            gr = build_message(Graph(), ACL['not-understood'], sender=GestorPaquets.uri, msgcnt=mss_cnt)
        else:
            if 'content' in msg:
                content = msg['content']
                accio = gm.value(subject=content, predicate=RDF.type)

                if accio == PANT.DemanarViatge:

                    # Ciutats destí i inici
                    ciutat_desti = gm.value(subject=content, predicate=PANT.teComAPuntFinal)
                    ciutat_d = str(gm.value(subject=ciutat_desti, predicate=PANT.nom))

                    ciutat_origen = gm.value(subject=content, predicate=PANT.teComAPuntInici)
                    ciutat_o = str(gm.value(subject=ciutat_origen, predicate=PANT.nom))

                    # Pressupost
                    pressupost = float(gm.value(subject=content, predicate=PANT.pressupost))

                    # Preferencia Allotjament
                    allotjament_centric = bool(gm.value(subject=content, predicate=PANT.allotjamentCentric))

                    # Dates viatge
                    data_ini = str(gm.value(subject=content, predicate=PANT.dataInici))
                    data_fi = str(gm.value(subject=content, predicate=PANT.dataFi))

                    # Preferències activitats
                    ludica = int(gm.value(subject=content, predicate=PANT.activitatsQuantLudiques))
                    cultural = int(gm.value(subject=content, predicate=PANT.activitatsQuantCulturals))
                    festiva = int(gm.value(subject=content, predicate=PANT.activitatsQuantFestives))

                    frangesObj = gm.triples((None, PANT.franja, None))
                    franges = []
                    for franja in frangesObj:
                        franges.append(str(franja[2]))

                    # Generar el paquet
                    content_paquet = generar_paquet(ciutat_o, ciutat_d, data_ini, data_fi, pressupost, ludica, festiva, cultural, allotjament_centric, franges)
                    gr = build_message(content_paquet,
                                       ACL['inform'],
                                       sender=GestorPaquets.uri,
                                       content=URIRef('https://paquetTancat.org'),
                                       msgcnt=mss_cnt,
                                       receiver=msg['sender'])

                else:
                    gr = build_message(Graph(), ACL['not-understood'], sender=GestorPaquets.uri, msgcnt=mss_cnt)

    mss_cnt += 1

    logger.info('Petició de paquet resposta')

    return gr.serialize(format='xml')


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

