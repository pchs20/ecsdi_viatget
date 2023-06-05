# -*- coding: utf-8 -*-
"""
Agent recol·lector de possibilitats d'allotjament
"""

from multiprocessing import Process, Queue
import logging
import argparse
import socket
import requests

from flask import Flask, request
from rdflib import Graph, Namespace, URIRef
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

    gr = registrar_agent(RecollectorAllotjaments, DirectoryAgent, agn.RecollectorAllotjaments, mss_cnt)

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
    message = request.args['content']
    gm = Graph()
    gm.parse(data=message, format='xml')
    msg = get_message_properties(gm)

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
                    centric = bool(gm.value(subject=content, predicate=PANT.centric))



                    # Obtenim les possibilitats i retornem la informació
                    possibilitats = obtenir_possibles_allotjaments(ciutat, data_ini, data_fi, preuMax, centric)
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


def refresh_allotjaments():
    logger.info('Fem refresh dels allotjaments que tenim guardats')
    logger.info(port)
    # Obtenim un actor extern d'allotjaments
    logger.info('Busquem un actor extern allotjaments')
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

    # Guardem les dades a la "BD"
    logger.info('Actualitzem la BD allotjaments')
    gr.serialize(destination='../bd/allotjaments.ttl', format='turtle')

    server_url = "http://localhost:3030"
    dataset_name = "Allotjaments"

    # Set the endpoint URL for updating the dataset
    update_url = f"{server_url}/{dataset_name}/data"

    # Set the RDF data file path
    rdf_file_path = "../bd/allotjaments.ttl"
    with open(rdf_file_path, "rb") as rdf_file:
        rdf_data = rdf_file.read()
    response = requests.post(update_url, data=rdf_data, headers={"Content-Type": "application/turtle"})

    # Check the response status
    if response.status_code == 200:
        print("RDF data saved successfully!")
    else:
        print(f"Failed to save RDF data. Status code: {response.status_code}")

    # Actualitzem la data de l'última actualització
    global ultimRefresh
    ultimRefresh = datetime.today()

def obtenir_possibles_allotjaments(ciutat, data_ini, data_fi, preuMax, centric):

    # Mirem si cal fer refresh de les dades: si l'últim refresh fa més d'un dia
    today = datetime.today()
    dif = today - ultimRefresh
    if dif > timedelta(days=1):
        refresh_allotjaments()

    # Escriure les dades de la bd
    server_url = "http://localhost:3030"
    dataset_name = "Allotjaments"

    query_url = f"{server_url}/{dataset_name}/get"
    response = requests.get(query_url)

    if response.status_code == 200:
        print("allotjaments.ttl file has been created successfully.")
    else:
        print(f"Failed to execute SPARQL query. Status code: {response.status_code}")


    # Recuperem les dades
    gbd = Graph()
    gbd.bind('PANT', PANT)
    gbd.parse(source='../bd/allotjaments.ttl', format='turtle')

    query = prepareQuery("""
        PREFIX pant:<https://ontologia.org#>
        SELECT ?Allotjament
        WHERE {
            ?Allotjament rdf:type pant:Allotjament .
            ?Allotjament pant:teCiutat ?ciutat .
            ?ciutat rdf:type pant:Ciutat .
            ?ciutat pant:nom ?nomCiutat .
            ?Allotjament pant:preu ?preu .
            ?Allotjament pant:centric ?centric .
            FILTER(?nomCiutat = "%s" && ?preu <= %s  && ?centric = %s)
        }
        ORDER BY ?preu
        LIMIT 5
    """ % (ciutat, preuMax, centric))



    resultados = gbd.query(query).result
    print('resultados = ', resultados)
    num_resultados = len(resultados)
    gr = Graph()
    gr.bind('PANT', PANT)

    for a in resultados:
        aObj = URIRef(a[0])
        gr.add((aObj, RDF.type, PANT.Allotjament))
        gr.add((aObj, PANT.nom, gbd.value(subject=aObj, predicate=PANT.nom)))
        gr.add((aObj, PANT.centric, gbd.value(subject=aObj, predicate=PANT.centric)))
        gr.add((aObj, PANT.teCiutat, gbd.value(subject=aObj, predicate=PANT.teCiutat)))
        gr.add((aObj, PANT.preu, gbd.value(subject=aObj, predicate=PANT.preu)))


    for resultado in resultados:
        enlace = resultado[0]
        if isinstance(enlace, URIRef):
            # Obtener el enlace como cadena de texto
            enlace_str = str(enlace)

            # Obtener el nombre del recurso (Allotjament)
            allotjament = enlace_str.split('/')[-1]

            # Obtener otros datos del recurso utilizando SPARQL
            query_datos = prepareQuery("""
                    PREFIX pant:<https://ontologia.org#>
                    SELECT ?nom ?preu ?ciutat
                    WHERE {
                        <%s> pant:nom ?nom ;
                            pant:preu ?preu ;
                            pant:teCiutat ?ciutat .
                    }
                """ % enlace_str)

            resultados_datos = gbd.query(query_datos)

            for resultado_datos in resultados_datos:
                nom = str(resultado_datos['nom'])
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
    refresh_allotjaments()

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
