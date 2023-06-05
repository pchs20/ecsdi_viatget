# -*- coding: utf-8 -*-
"""
Actor extern proveïdor d'activitats
"""

from multiprocessing import Process, Queue
import logging
import argparse
import socket

from flask import Flask, request
from rdflib import Graph, Namespace, Literal, URIRef
from rdflib.namespace import RDF

from utils.FlaskServer import shutdown_server
from utils.ACLMessages import build_message, get_message_properties
from utils.Agent import Agent
from utils.Logging import config_logger
from utils.Util import gethostname, registrar_agent

from ontologies.ACL import ACL
from ontologies.Viatget import PANT

from amadeus import Client
from utils.APIKeys import AMADEUS_KEY, AMADEUS_SECRET


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
    port = 9032
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
ProveidorActivitats = Agent('ProveidorActivitats2',
                  agn.ProveidorActivitats2,
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
amadeus = Client(
    client_id=AMADEUS_KEY,
    client_secret=AMADEUS_SECRET
)


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

    gr = registrar_agent(ProveidorActivitats, DirectoryAgent, agn.ActorActivitats, mss_cnt)

    mss_cnt += 1

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
    global dsgraph
    global mss_cnt

    logger.info('Petició per obtenir totes les activitats rebuda')

    # Extraemos el mensaje y creamos un grafo con el
    message = request.args['content']
    gm = Graph()
    gm.parse(data=message, format="xml")
    msg = get_message_properties(gm)

    # Comprobamos que sea un mensaje FIPA ACL
    if msg is None:
        # Si no es, respondemos que no hemos entendido el mensaje
        gr = build_message(Graph(), ACL['not-understood'], sender=ProveidorActivitats.uri, msgcnt=mss_cnt)
    else:
        # Obtenemos la performativa
        perf = msg['performative']

        if perf != ACL.request:
            # Si no es un request, respondemos que no hemos entendido el mensaje
            gr = build_message(Graph(), ACL['not-understood'], sender=ProveidorActivitats.uri, msgcnt=mss_cnt)
        else:
            # Averiguamos el tipo de la accion
            if 'content' in msg:
                content = msg['content']
                accio = gm.value(subject=content, predicate=RDF.type)

                # PROCÉS DE TRACTAMENT DE LA REQUEST

                if accio == PANT.ObtenirActivitats:
                    activitats = obtenir_activitats()
                    gr = build_message(activitats,
                                       ACL['inform'],
                                       sender=ProveidorActivitats.uri,
                                       msgcnt=mss_cnt,
                                       receiver=msg['sender'])
                else:
                    # Si no és una petició d'activitats
                    gr = build_message(Graph(), ACL['not-understood'], sender=ProveidorActivitats.uri,
                                       msgcnt=mss_cnt)
    mss_cnt += 1

    logger.info('Petició per obtenir activitats resposta')

    return gr.serialize(format='xml')


def obtenir_activitats():
    ciutats = ["BCN", "BER"]

    gr = Graph()
    gr.bind('PANT', PANT)

    # Per ara, ens inventem les dades
    bcn = URIRef('https://ciutats.org/Barcelona')
    gr.add((bcn, RDF.type, PANT.Ciutat))
    gr.add((bcn, PANT.nom, Literal('Barcelona')))

    ber = URIRef('https://ciutats.org/Berlin')
    gr.add((ber, RDF.type, PANT.Ciutat))
    gr.add((ber, PANT.nom, Literal('Berlin')))

    ciutatsObj = {
        "BCN": bcn,
        "BER": ber
    }

    tipusActivitats = ["cultural", "ludica", "festiva"]

    franges = ["mati", "tarda", "nit"]

    activitats = {
        "BCN": {
            "cultural": {
                "mati": [
                    "Visitar la Sagrada Família",
                    "Explorar el Park Güell",
                    "Passejar pel Barri Gòtic",
                    "Visitar el Museu Picasso",
                    "Fer una visita al Museu Nacional d'Art de Catalunya",
                    "Descobrir l'Arxiu Històric de la Ciutat",
                    "Fer una ruta modernista",
                    "Visitar la Fundació Joan Miró",
                    "Explorar el Mercat de Sant Josep de la Boqueria",
                    "Passejar pel Parc de la Ciutadella",
                    "Visitar el Palau de la Música Catalana",
                    "Descobrir el Monestir de Pedralbes",
                    "Explorar el Museu d'Història de Barcelona",
                    "Passejar pel Passeig de Gràcia",
                    "Visitar el Castell de Montjuïc",
                    "Descobrir el Museu d'Art Contemporani de Barcelona",
                    "Fer una visita al Museu Marítim de Barcelona",
                    "Explorar el Palau Güell",
                    "Passejar per la Platja de la Barceloneta",
                    "Visitar el Museu d'Història de Catalunya",
                    "Descobrir la Casa Batlló",
                    "Explorar el Parc de la Pedralbes",
                    "Passejar pel Parc de la Creueta del Coll",
                    "Visitar la Fundació Antoni Tàpies",
                    "Descobrir el Museu de la Música",
                    "Explorar el Museu del Disseny de Barcelona",
                    "Passejar pel Parc del Laberint d'Horta",
                    "Visitar la Casa Vicens",
                    "Descobrir el Museu del Modernisme Català",
                    "Explorar el Museu del Perfum",
                    "Passejar per la Rambla",
                    "Visitar el Museu de la Xocolata",
                    "Descobrir el Jardí Botànic de Barcelona",
                    "Explorar el Museu de la Cera",
                    "Passejar pel Parc de la Guineueta",
                    "Visitar la Casa de les Punxes",
                    "Descobrir el Museu Egipci de Barcelona",
                    "Explorar el Mercat de Sant Antoni",
                    "Passejar pel Parc de la Barceloneta",
                    "Visitar el CosmoCaixa Barcelona",
                    "Descobrir el Museu del FC Barcelona",
                    "Explorar el Museu de Ciències Naturals de Barcelona",
                    "Passejar pel Parc de la Trinitat",
                    "Visitar el Museu de la Moto de Barcelona",
                    "Descobrir el Museu de l'Erotisme",
                    "Explorar el Museu Frederic Marès",
                    "Passejar pel Parc de la Ciutadella",
                    "Visitar el Museu del Disseny de Barcelona",
                    "Descobrir el Centre de Cultura Contemporània de Barcelona",
                    "Explorar el Museu dels Autòmats del Tibidabo",
                    "Passejar pel Parc de la Creueta del Coll"
                ],
                "tarda": [
                    "Fer un recorregut pel Camp Nou",
                    "Gaudir d'una actuació al Palau de la Música Catalana",
                    "Visitar el Museu Nacional d'Art de Catalunya",
                    "Passejar pel Passeig de Gràcia",
                    "Explorar el Park Güell",
                    "Fer una ruta gastronòmica pel Barri Gòtic",
                    "Visitar el Museu Picasso",
                    "Gaudir d'un espectacle al Teatre Lliure",
                    "Explorar el Palau Güell",
                    "Passejar per la Platja de la Barceloneta",
                    "Visitar el Museu d'Història de Catalunya",
                    "Gaudir d'una pel·lícula al Cinema Maldà",
                    "Explorar el Mercat de Sant Antoni",
                    "Passejar pel Parc de la Barceloneta",
                    "Visitar el Museu Marítim de Barcelona",
                    "Gaudir d'un concert al Palau Sant Jordi",
                    "Explorar el Museu d'Història de Barcelona",
                    "Passejar pel Parc de la Ciutadella",
                    "Visitar el Museu del Disseny de Barcelona",
                    "Gaudir d'una actuació al Gran Teatre del Liceu",
                    "Explorar el Mercat de Sant Josep de la Boqueria",
                    "Passejar pel Parc del Laberint d'Horta",
                    "Visitar el CosmoCaixa Barcelona",
                    "Gaudir d'un espectacle al Teatre Nacional de Catalunya",
                    "Explorar el Mercat de la Boqueria",
                    "Passejar pel Parc de la Creueta del Coll",
                    "Visitar la Fundació Joan Miró",
                    "Gaudir d'un concert al Palau de la Música Catalana",
                    "Explorar el Mercat de Sant Antoni",
                    "Passejar pel Parc de la Barceloneta",
                    "Visitar el Museu d'Art Contemporani de Barcelona",
                    "Gaudir d'una obra de teatre al Teatre Romea",
                    "Explorar el Museu de Ciències Naturals de Barcelona",
                    "Passejar pel Parc de la Ciutadella",
                    "Visitar el Museu de la Xocolata",
                    "Gaudir d'un espectacle al Teatre Condal",
                    "Explorar el Mercat de Sant Josep de la Boqueria",
                    "Passejar pel Parc del Laberint d'Horta",
                    "Visitar la Fundació Antoni Tàpies",
                    "Gaudir d'un concert al Palau Sant Jordi",
                    "Explorar el Mercat de la Boqueria",
                    "Passejar pel Parc de la Creueta del Coll",
                    "Visitar el Museu Frederic Marès",
                    "Gaudir d'una actuació al Teatre Grec",
                    "Explorar el Museu del Disseny de Barcelona",
                    "Passejar pel Parc de la Barceloneta",
                    "Visitar el Museu del Modernisme Català",
                    "Gaudir d'una pel·lícula al Cinema Maldà",
                    "Explorar el Mercat de Sant Antoni",
                    "Passejar pel Parc de la Barceloneta",
                    "Visitar el Museu de la Música",
                    "Gaudir d'un espectacle al Teatre Nacional de Catalunya"
                ],
                "nit": [
                    "Descobrir la vida nocturna al barri del Raval",
                    "Gaudir d'una nit de flamenc al Tablao de Carmen",
                    "Explorar els bars musicals del Poble-sec",
                    "Fer un recorregut pels bars de tapes a la Barceloneta",
                    "Gaudir d'un espectacle de música en viu a JazzSí Club",
                    "Explorar els clubs de música electrònica a Poble Nou",
                    "Bailar salsa i altres ritmes llatins al Pirata Barcelona",
                    "Gaudir d'un espectacle de teatre al Teatre Apolo",
                    "Explorar els bars de cocktails a El Born",
                    "Fer una ruta de còctels a l'Eixample",
                    "Gaudir d'un espectacle de flamenc a El Tablao de Carmen",
                    "Explorar els bars de cervesa artesana a Gràcia",
                    "Bailar fins a l'alba a la Sala Apolo",
                    "Gaudir d'un concert de música en viu a la Sala Razzmatazz",
                    "Explorar els bars de jazz a l'Esquerra de l'Eixample",
                    "Fer una ruta de gin-tonics al Poblenou",
                    "Gaudir d'una nit de karaoke al Espai Erre de Rumba",
                    "Explorar els bars de música indie a Sant Antoni",
                    "Bailar música reggaeton a La Fira Barcelona",
                    "Gaudir d'un espectacle de comèdia al Teatre Condal",
                    "Explorar els clubs de música hip-hop a Gràcia",
                    "Fer una ruta de vins a l'Enoteca Barcelona",
                    "Gaudir d'una nit de jazz a Jamboree Jazz Club",
                    "Explorar els bars de cocktails a El Raval",
                    "Bailar música latina al Antilla BCN",
                    "Gaudir d'un espectacle de música en viu a Harlem Jazz Club",
                    "Explorar els clubs de música techno a Sant Gervasi",
                    "Fer una ruta de vermuts a Poble Nou",
                    "Gaudir d'una nit de música flamenca al Palau de la Música",
                    "Explorar els bars de música en directe a Gràcia",
                    "Bailar música electrònica a Input High Fidelity Dance Club",
                    "Gaudir d'un espectacle de teatre al Teatre Lliure",
                    "Explorar els clubs de música rock a Sants",
                    "Fer una ruta de cerveses a Sant Antoni",
                    "Gaudir d'una nit de música indie al Razzmatazz",
                    "Explorar els bars de cocktails a Poble-sec",
                    "Bailar música reggae al Marula Café",
                    "Gaudir d'un espectacle de flamenc al Palau Dalmases",
                    "Explorar els clubs de música house a Gràcia",
                    "Fer una ruta de vins a El Born",
                    "Gaudir d'una nit de música en viu a Sidecar Factory Club",
                    "Explorar els bars de música en directe a Raval",
                    "Bailar música latina al Mojito Club Barcelona",
                    "Gaudir d'un espectacle de jazz al Jamboree Jazz Club",
                    "Explorar els clubs de música hip-hop a Poble-sec",
                    "Fer una ruta de gin-tonics a Gràcia",
                    "Explorar els bars de cocktails a Poble-sec",
                    "Bailar música reggae al Marula Café",
                    "Gaudir d'un espectacle de flamenc al Palau Dalmases",
                    "Explorar els clubs de música house a Gràcia",
                    "Fer una ruta de vins a El Born"
                ]
            },
            "ludica": {
                "mati": [
                    "Fer una caminada per la platja de la Barceloneta",
                    "Visitar el Parc Güell",
                    "Fer un recorregut en bicicleta pel parc de la Ciutadella",
                    "Explorar el barri gòtic i visitar la Catedral de Barcelona",
                    "Fer un passeig pel parc de Montjuïc i visitar el Castell de Montjuïc",
                    "Anar de compres al Passeig de Gràcia",
                    "Visitar el Museu Picasso",
                    "Explorar el Mercat de Sant Josep de la Boqueria",
                    "Fer una visita al Palau de la Música Catalana",
                    "Anar a l'Aquàrium de Barcelona",
                    "Fer un recorregut en kayak pel Port Olímpic",
                    "Visitar el Museu Nacional d'Art de Catalunya",
                    "Explorar el Park Güell",
                    "Anar a la platja de Nova Icaria",
                    "Fer una visita al Mercat de Sant Antoni",
                    "Visitar la Casa Batlló",
                    "Explorar el laberint d'Horta",
                    "Fer un passeig pel parc del Laberint d'Horta",
                    "Anar a la platja de Bogatell",
                    "Visitar el Museu d'Història de Barcelona",
                    "Explorar el Parc de la Ciutadella",
                    "Fer una visita a la Sagrada Família",
                    "Anar a la platja de Sant Sebastià",
                    "Visitar el Museu d'Art Contemporani de Barcelona",
                    "Explorar el barri de Gràcia",
                    "Fer una excursió al Tibidabo",
                    "Anar a la platja de Barceloneta",
                    "Visitar el Museu Marítim de Barcelona",
                    "Explorar el Camp Nou i el Museu del Futbol Club Barcelona",
                    "Fer un passeig pel carrer Passeig de Sant Joan",
                    "Anar a la platja de Mar Bella",
                    "Visitar el Museu Europeu d'Art Modern",
                    "Explorar el barri de Sant Antoni",
                    "Fer una visita al Palau Güell",
                    "Anar a la platja de Somorrostro",
                    "Visitar el Museu de la Xocolata",
                    "Explorar el barri del Raval",
                    "Fer una excursió al Parc de la Serralada de Marina",
                    "Anar a la platja de Nova Mar Bella",
                    "Visitar el Museu de la Música",
                    "Explorar el barri de Sant Pere, Santa Caterina i la Ribera",
                    "Fer una visita al Poble Espanyol",
                    "Anar a la platja de Llevant",
                    "Visitar el Museu del Disseny de Barcelona",
                    "Explorar el barri de Sant Martí",
                    "Fer una excursió al Parc de Collserola",
                    "Anar a la platja de la Nova Icaria",
                    "Visitar el Museu de Cera de Barcelona",
                    "Fer una visita al Mercat de Sant Antoni",
                    "Visitar la Casa Batlló",
                    "Explorar el laberint d'Horta"
                ],
                "tarda": [
                    "Fer un tour en segway per Barcelona",
                    "Explorar el barri de Poblenou",
                    "Anar de compres al Centre Comercial Les Glòries",
                    "Fer una visita al Museu del Modernisme Català",
                    "Anar a la platja de la Barceloneta i gaudir d'un bany de sol",
                    "Fer un recorregut en vaixell per la costa de Barcelona",
                    "Visitar el Zoo de Barcelona",
                    "Explorar el barri de El Born",
                    "Anar a la platja de Sant Miquel",
                    "Fer una visita a l'Estadi Olímpic de Barcelona",
                    "Fer una ruta gastronòmica per provar les tapes de Barcelona",
                    "Anar a la platja de la Nova Mar Bella i practicar esports aquàtics",
                    "Fer una visita al Museu de la Cervesa",
                    "Explorar el barri de Sant Andreu",
                    "Anar a la platja de la Nova Mar Bella i relaxar-se en una de les terrasses",
                    "Fer una visita al Museu de la Moto de Barcelona",
                    "Anar a la platja de la Barceloneta i fer una paella a un restaurant de la zona",
                    "Fer una visita al Museu de la Xocolata i degustar xocolata artesana",
                    "Anar a la platja de la Nova Icaria i practicar beach volley",
                    "Fer una visita a l'Aquàrium de Barcelona i veure l'espectacle de dofins",
                    "Anar a la platja de Nova Icaria i fer una ruta en patinet elèctric",
                    "Fer una visita al Museu Marítim de Barcelona i veure les embarcacions antigues",
                    "Anar a la platja de Sant Sebastià i fer una sessió de ioga a la sorra",
                    "Fer una visita a la Casa Batlló i admirar l'arquitectura modernista",
                    "Anar a la platja de Somorrostro i fer un partit de vòlei platja",
                    "Fer una visita al Museu d'Història de Barcelona i conèixer la història de la ciutat",
                    "Anar a la platja de Mar Bella i fer una ruta en patinet",
                    "Fer una visita al Museu d'Art Contemporani de Barcelona i veure les exposicions actuals",
                    "Anar a la platja de Barceloneta i gaudir d'una copa en un xiringuito",
                    "Fer una visita al Museu Picasso i descobrir les seves obres mestres",
                    "Anar a la platja de Bogatell i fer una sessió de ioga a la platja",
                    "Fer una visita al Mercat de Sant Josep de la Boqueria i tastar els seus productes",
                    "Anar a la platja de Nova Icaria i fer una passejada en patinet elèctric",
                    "Fer una visita al Parc de la Ciutadella i relaxar-se al seu parc",
                    "Anar a la platja de Sant Sebastià i gaudir d'un pícnic a la sorra",
                    "Fer una visita al Museu Nacional d'Art de Catalunya i contemplar les seves obres d'art",
                    "Anar a la platja de Somorrostro i fer un vol en parasailing",
                    "Fer una visita a la Sagrada Família i explorar l'arquitectura de Gaudí",
                    "Anar a la platja de Mar Bella i fer una sessió de surf",
                    "Fer una visita al Park Güell i gaudir de les vistes panoràmiques de la ciutat",
                    "Anar a la platja de Barceloneta i fer una classe de ioga a la platja",
                    "Fer una visita al Museu d'Història de Barcelona i explorar els seus jardins",
                    "Anar a la platja de Bogatell i practicar paddle surf",
                    "Fer una visita al Museu d'Art Contemporani de Barcelona i veure les seves instal·lacions",
                    "Anar a la platja de Nova Mar Bella i fer un massatge relaxant a la platja",
                    "Fer una visita al Parc de la Ciutadella i fer un passeig en barca pel seu llac",
                    "Anar a la platja de Sant Sebastià i gaudir d'un espectacle de música en viu",
                    "Fer una visita al Museu Nacional d'Art de Catalunya i veure les seves exposicions temporals",
                    "Anar a la platja de Somorrostro i fer una ruta en bicicleta per la costa",
                    "Fer una visita a la Sagrada Família i assistir a una missa",
                    "Anar a la platja de Mar Bella i gaudir d'un joc de vòlei platja",
                    "Fer una visita al Park Güell i fer un pícnic en un dels seus jardins",
                    "Anar a la platja de Barceloneta i practicar surf",
                    "Fer una visita al Museu Picasso i aprendre sobre la vida de l'artista",
                    "Anar a la platja de Bogatell i fer una sessió de tai-chi a la platja"
                ],
                "nit": [
                    "Anar a un espectacle de flamenc",
                    "Gaudir d'un sopar romàntic a la platja",
                    "Anar a un concert en un dels clubs de música en viu de Barcelona",
                    "Explorar els bars de tapes al barri de Gràcia",
                    "Fer una visita nocturna a la Sagrada Família",
                    "Gaudir d'una copa de cava en una terrassa amb vistes a la ciutat",
                    "Anar a una festa a la platja de Barceloneta",
                    "Explorar el barri de El Raval i provar alguns dels seus bars i restaurants",
                    "Fer una ruta de bar en bar per la zona del Born",
                    "Gaudir d'una nit de flamenc en un dels tablao de la ciutat",
                    "Anar a una discoteca a la zona del Port Olímpic",
                    "Explorar els bars de cocktails al barri de Poble Sec",
                    "Fer una visita nocturna al parc Güell i veure les vistes nocturnes de Barcelona",
                    "Gaudir d'un concert de música clàssica al Palau de la Música Catalana",
                    "Anar a una terrassa amb música en viu a la plaça Reial",
                    "Explorar els clubs de jazz al barri de Gràcia",
                    "Fer una ruta de vins per les cellers de Barcelona",
                    "Gaudir d'una nit de rumba catalana al barri de Poble-sec",
                    "Anar a una discoteca a la zona del Raval",
                    "Explorar els bars de cocktails al barri del Gòtic",
                    "Fer una visita nocturna a la Casa Batlló i veure la seva il·luminació nocturna",
                    "Gaudir d'un espectacle de magia en un dels teatres de la ciutat",
                    "Anar a una festa a la platja de Nova Icaria",
                    "Explorar els bars de música indie al barri de Sant Antoni",
                    "Fer una ruta gastronòmica per provar plats típics catalans",
                    "Gaudir d'una nit de música electrònica en un dels clubs de Barcelona",
                    "Anar a una discoteca a la zona del Poble-sec",
                    "Explorar els bars de cocktails al barri de Gràcia",
                    "Fer una visita nocturna al Museu Picasso",
                    "Gaudir d'una nit de jazz en un dels clubs de la ciutat",
                    "Anar a una terrassa amb música en viu al barri del Born",
                    "Explorar els bars de música en directe al barri del Raval",
                    "Fer una ruta de tapas per provar la gastronomia local",
                    "Gaudir d'un espectacle de comèdia en un dels teatres de Barcelona",
                    "Anar a una festa a la platja de Sant Miquel",
                    "Explorar els bars de cocktails al barri de Poblenou",
                    "Fer una visita nocturna a la Casa Milà i veure el seu espectacle nocturn",
                    "Gaudir d'una nit de música flamenca en un dels peña flamencas de la ciutat",
                    "Anar a una discoteca a la zona del Gràcia",
                    "Explorar els bars de música en directe al barri de Sant Antoni",
                    "Fer una ruta de vermuts per provar les vermuteries tradicionals",
                    "Gaudir d'una nit de música en viu en un dels clubs de música de Barcelona",
                    "Fer una visita nocturna a la Casa Batlló i veure la seva il·luminació nocturna",
                    "Gaudir d'un espectacle de magia en un dels teatres de la ciutat",
                    "Anar a una festa a la platja de Nova Icaria",
                    "Explorar els bars de música indie al barri de Sant Antoni",
                    "Fer una ruta gastronòmica per provar plats típics catalans",
                    "Gaudir d'una nit de música electrònica en un dels clubs de Barcelona",
                    "Anar a una discoteca a la zona del Poble-sec",
                    "Explorar els bars de cocktails al barri de Gràcia",
                    "Fer una visita nocturna al Museu Picasso",
                    "Gaudir d'una nit de jazz en un dels clubs de la ciutat",
                    "Anar a una terrassa amb música en viu al barri del Born",
                    "Explorar els bars de música en directe al barri del Raval"
                ]
            },
            "festiva": {
                "mati": [
                    "Assistir a una cercavila de gegants",
                    "Participar en una classe de ioga al parc",
                    "Fer una visita guiada al Barri Gòtic",
                    "Gaudir d'un esmorzar en una terrassa del Passeig de Gràcia",
                    "Fer un recorregut en bicicleta per la platja de Barceloneta",
                    "Visitar el Parc de la Ciutadella i fer un pícnic",
                    "Explorar el Mercat de Sant Josep de la Boqueria",
                    "Fer una caminada per la muntanya de Montjuïc",
                    "Visitar el Museu Picasso",
                    "Assistir a un concert matinal al Palau de la Música Catalana",
                    "Fer un taller de ceràmica al Poble Espanyol",
                    "Explorar l'Arxiu Fotogràfic de Barcelona",
                    "Fer una ruta gastronòmica pel barri de Gràcia",
                    "Visitar la Fundació Joan Miró",
                    "Fer un passeig en vaixell per la costa de Barcelona",
                    "Assistir a una representació de teatre al Teatre Lliure",
                    "Fer una visita al Camp Nou i al Museu del Futbol Club Barcelona",
                    "Explorar el Museu Nacional d'Art de Catalunya (MNAC)",
                    "Gaudir d'una sessió de cinema a l'aire lliure",
                    "Visitar el Monestir de Pedralbes",
                    "Fer una ruta de tapas pel barri del Raval",
                    "Assistir a una classe de cuina catalana tradicional",
                    "Explorar el Parc Güell",
                    "Fer una visita al Palau Güell",
                    "Gaudir d'un esmorzar típic català amb pa amb tomàquet i embotits",
                    "Fer una ruta de compras pels carrers comercials del Passeig de Gràcia",
                    "Visitar el Museu d'Història de Barcelona (MUHBA)",
                    "Assistir a un espectacle de dansa flamenca",
                    "Fer un taller de fabricació de cervesa artesana",
                    "Explorar el Barri de la Barceloneta i gaudir de la platja",
                    "Visitar el Mercat de Sant Antoni",
                    "Fer una excursió al Parc Natural de Collserola",
                    "Gaudir d'un brunch en un dels restaurants de moda de Barcelona",
                    "Assistir a un concert de música clàssica al Palau de la Música",
                    "Fer una visita al Museu d'Art Contemporani de Barcelona (MACBA)",
                    "Explorar el barri de Sant Pere, Santa Caterina i la Ribera",
                    "Visitar la Casa Batlló de Gaudí",
                    "Fer un taller de ceràmica al taller d'un artesà",
                    "Assistir a una classe de flamenc",
                    "Gaudir d'un bany a les platges de Nova Icaria o Bogatell",
                    "Visitar el Museu Marítim de Barcelona",
                    "Fer una ruta de vins pels cellers del Penedès",
                    "Explorar el barri del Born i visitar el Mercat del Born",
                    "Assistir a un espectacle de música en directe al Palau de la Música",
                    "Fer una visita a l'Aquàrium de Barcelona",
                    "Gaudir d'un espectacle de circ al Teatre Nacional de Catalunya",
                    "Visitar el Castell de Montjuïc",
                    "Fer un taller de pastisseria tradicional catalana",
                    "Explorar el parc del Laberint d'Horta",
                    "Assistir a una exposició d'art contemporani al Centre de Cultura Contemporània de Barcelona (CCCB)"
                ],
                "tarda": [
                    "Fer una visita a la Sagrada Família",
                    "Gaudir d'un vermut en una terrassa del Poble Sec",
                    "Explorar el barri de Sant Antoni i visitar el Mercat de Sant Antoni",
                    "Assistir a un espectacle de flamenc al Tablao de Carmen",
                    "Fer una ruta de tast de formatges catalans",
                    "Visitar el Palau de la Música Catalana",
                    "Fer un taller de cocteleria al Born",
                    "Explorar el parc de la Ciutadella en bicicleta",
                    "Assistir a un espectacle de música al Palau Sant Jordi",
                    "Fer una ruta de còctels per bars de moda a la Vila de Gràcia",
                    "Visitar la Casa Milà (La Pedrera)",
                    "Fer una visita al Museu Europeu d'Art Modern (MEAM)",
                    "Gaudir d'un pícnic al parc de la Barceloneta",
                    "Assistir a una representació de dansa al Gran Teatre del Liceu",
                    "Fer una ruta de tapas per la zona del Poble-sec",
                    "Visitar el Museu d'Arqueologia de Catalunya",
                    "Explorar el barri de Sarrià i visitar el Monestir de Santa Maria de Pedralbes",
                    "Assistir a un espectacle de música en directe al Razzmatazz",
                    "Fer una visita a la Fundació Antoni Tàpies",
                    "Gaudir d'un espectacle de màgia al Teatre Victòria",
                    "Fer una ruta gastronòmica per la zona del Born",
                    "Visitar el Museu de la Xocolata",
                    "Assistir a una obra de teatre al Teatre Nacional de Catalunya",
                    "Fer una excursió en vaixell fins a les platges de Sitges",
                    "Explorar el barri de Gràcia i visitar el Parc de la Creueta del Coll",
                    "Visitar el CosmoCaixa, el Museu de la Ciència de Barcelona",
                    "Assistir a un concert de música moderna al Palau Sant Jordi",
                    "Fer una ruta de vins pels cellers del Priorat",
                    "Gaudir d'una cervesa artesana en un dels bars de la Raval",
                    "Fer una visita a la Catedral de Barcelona",
                    "Explorar el barri del Raval i visitar el MACBA",
                    "Assistir a una representació de teatre al Teatre Romea",
                    "Fer una visita a la Torre Bellesguard de Gaudí",
                    "Visitar el Museu Nacional d'Art de Catalunya (MNAC)",
                    "Assistir a un espectacle de dansa contemporània al Mercat de les Flors",
                    "Fer una ruta gastronòmica per la zona de Poble-sec",
                    "Visitar el Museu de la Música",
                    "Assistir a un concert de música clàssica a l'Auditori de Barcelona",
                    "Fer una visita al Jardí Botànic de Barcelona",
                    "Explorar el barri de Sant Pere, Santa Caterina i la Ribera i visitar el Palau de la Música Catalana",
                    "Gaudir d'una tarda de relaxació en un spa",
                    "Fer una excursió a la muntanya de Montserrat",
                    "Assistir a un espectacle de flamenc al Palau de la Música Catalana",
                    "Visitar el Museu Picasso",
                    "Explorar el barri de Gràcia i visitar el Park Güell",
                    "Assistir a una exhibició de castells a la plaça de Sant Jaume",
                    "Assistir a una representació de teatre al Teatre Romea",
                    "Fer una visita a la Torre Bellesguard de Gaudí",
                    "Visitar el Museu Nacional d'Art de Catalunya (MNAC)",
                    "Assistir a un espectacle de dansa contemporània al Mercat de les Flors",
                    "Fer una ruta gastronòmica per la zona de Poble-sec",
                    "Visitar el Museu de la Música",
                    "Assistir a un concert de música clàssica a l'Auditori de Barcelona",
                    "Fer una visita al Jardí Botànic de Barcelona",
                    "Explorar el barri de Sant Pere, Santa Caterina i la Ribera i visitar el Palau de la Música Catalana",
                    "Gaudir d'una tarda de relaxació en un spa"
                ],
                "nit": [
                    "Gaudir d'un sopar en un restaurant amb estrella Michelin",
                    "Bailar en una discoteca a la platja de la Barceloneta",
                    "Assistir a un concert en directe al Palau Sant Jordi",
                    "Fer una ruta de còctels per bars de moda al barri Gòtic",
                    "Visitar el Poble Espanyol i gaudir de les seves activitats nocturnes",
                    "Explorar els mercats nocturns de Barcelona, com el Mercat de Sant Antoni o el Mercat de la Boqueria",
                    "Assistir a un espectacle de flamenc a Tablao Cordobés",
                    "Fer una ruta de bars de tapes per la zona del Raval",
                    "Visitar el Castell de Montjuïc de nit i gaudir de les seves vistes panoràmiques",
                    "Explorar el barri del Poble-sec i gaudir de la seva oferta gastronòmica nocturna",
                    "Assistir a una sessió de música en directe al Jamboree Jazz Club",
                    "Fer una visita nocturna a la Sagrada Família",
                    "Gaudir d'un espectacle de flamenc al Tablao de Carmen",
                    "Assistir a una representació de teatre al Teatre Lliure de Gràcia",
                    "Fer una ruta de còctels per bars de moda a la Vila de Gràcia",
                    "Visitar el Museu del Disseny de Barcelona de nit",
                    "Explorar el barri del Born i gaudir del seu ambient nocturn",
                    "Assistir a un concert de música electrònica al Razzmatazz",
                    "Fer una ruta de bars de cocktails per la zona de Sant Antoni",
                    "Visitar la Casa Batlló de nit",
                    "Gaudir d'un espectacle de màgia al Teatre Victòria",
                    "Assistir a una projecció de cinema a l'aire lliure",
                    "Fer una visita nocturna al Parc Güell",
                    "Explorar el barri del Raval i gaudir de la seva vida nocturna",
                    "Assistir a un espectacle de música en directe al Palau de la Música",
                    "Visitar el Museu d'Història de Barcelona (MUHBA) de nit",
                    "Fer una ruta de còctels per bars de moda al barri del Born",
                    "Gaudir d'una nit de festa al Poble Espanyol",
                    "Assistir a un espectacle de flamenc al Palau de la Música Catalana",
                    "Visitar el Museu d'Art Contemporani de Barcelona (MACBA) de nit",
                    "Explorar el barri de Gràcia i gaudir de la seva vida nocturna",
                    "Gaudir d'un espectacle de flamenc al Tablao de Carmen",
                    "Assistir a una representació de teatre al Teatre Lliure de Gràcia",
                    "Fer una ruta de còctels per bars de moda a la Vila de Gràcia",
                    "Visitar el Museu del Disseny de Barcelona de nit",
                    "Explorar el barri del Born i gaudir del seu ambient nocturn",
                    "Assistir a un concert de música electrònica al Razzmatazz",
                    "Fer una ruta de bars de cocktails per la zona de Sant Antoni",
                    "Visitar la Casa Batlló de nit",
                    "Gaudir d'un espectacle de màgia al Teatre Victòria",
                    "Assistir a una projecció de cinema a l'aire lliure",
                    "Fer una visita nocturna al Parc Güell",
                    "Explorar el barri del Raval i gaudir de la seva vida nocturna",
                    "Gaudir d'un sopar en un restaurant amb estrella Michelin",
                    "Bailar en una discoteca a la platja de la Barceloneta",
                    "Assistir a un concert en directe al Palau Sant Jordi",
                    "Fer una ruta de còctels per bars de moda al barri Gòtic",
                    "Visitar el Poble Espanyol i gaudir de les seves activitats nocturnes",
                    "Explorar els mercats nocturns de Barcelona, com el Mercat de Sant Antoni o el Mercat de la Boqueria",
                    "Assistir a un espectacle de flamenc a Tablao Cordobés",
                    "Fer una ruta de bars de tapes per la zona del Raval"
                ]
            }
        },
        "BER": {
            "cultural": {
                "mati": [
                    "Visita al Museu de Pergamó",
                    "Passeig per l'illa dels Museus",
                    "Recorregut pel Muro de Berlín",
                    "Visita a la Catedral de Berlín",
                    "Exploració del Jardí Zoològic de Berlín",
                    "Visita a la Topografia del Terror",
                    "Recorregut pel Reichstag",
                    "Passeig per Unter den Linden",
                    "Visita a l'East Side Gallery",
                    "Exploració del Mercat de Mauerpark",
                    "Visita al Monument del Memorial del Holocaust",
                    "Recorregut pel Districte dels Museus",
                    "Passeig pel Parc Tiergarten",
                    "Visita al Museu de la DDR",
                    "Exploració de la Ópera Alemanya de Berlín",
                    "Passeig per la Plaça Alexanderplatz",
                    "Visita al Museu Bode",
                    "Recorregut pel Barri Nikolai",
                    "Visita al Palau de Charlottenburg",
                    "Exploració del Cementiri Jueu de Berlín",
                    "Passeig per la Plaça Gendarmenmarkt",
                    "Visita a la Gemäldegalerie",
                    "Recorregut pel Museu de Tecnologia",
                    "Passeig pel Parc Görlitzer",
                    "Visita al Museu Bauhaus",
                    "Exploració de la Casa de l'Estudiantat",
                    "Passeig per la Plaça de Potsdamer",
                    "Visita a l'Escola de Belles Arts de Berlín",
                    "Recorregut pel Memorial a Rosa Luxemburg",
                    "Passeig per la Plaça de la República",
                    "Visita al Museu Històric de Berlín",
                    "Exploració del Palau de la República",
                    "Passeig pel Barri de Kreuzberg",
                    "Visita al Museu de la Màquina d'Escriure",
                    "Recorregut pel Parc Viktoriapark",
                    "Passeig pel Districte de Prenzlauer Berg",
                    "Visita al Museu de la Tecnologia Espacial",
                    "Exploració de la Torre de la Televisió",
                    "Passeig per la Plaça Hackescher Markt",
                    "Visita al Museu del Còmic i la Dibuixant",
                    "Recorregut pel Cementiri de Dorotheenstadt",
                    "Passeig pel Districte de Friedrichshain",
                    "Visita al Museu de la Resistència Alemanya",
                    "Exploració dels Jardins de Charlottenburg",
                    "Passeig per la Plaça Bebelplatz",
                    "Visita al Museu de Ciències Naturals",
                    "Recorregut pel Parc Treptower",
                    "Passeig pel Barri de Mitte",
                    "Visita a la Galeria d'Art KW Institute",
                    "Exploració de l'Estació Central de Berlín",
                    "Passeig per la Plaça Rosa Luxemburg",
                    "Visita al Museu de l'Esperanto",
                    "Passeig per la Plaça Potsdam",
                ],
                "tarda": [
                    "Recorregut pel Districte de Moabit",
                    "Visita a la Galeria d'Art Sammlung Boros",
                    "Exploració de l'Antic Cementiri de St. Matthew",
                    "Passeig pel Barri de Schöneberg",
                    "Visita al Museu de la Muralla de Berlín",
                    "Recorregut pel Parc Hasenheide",
                    "Passeig per la Plaça Kollwitzplatz",
                    "Visita a l'Edifici Sony Center",
                    "Exploració del Cementiri de St. Hedwig",
                    "Passeig pel Barri de Wedding",
                    "Visita al Museu del Cine de Berlín",
                    "Recorregut pel Parc Friedrichshain",
                    "Passeig per la Plaça Görli",
                    "Visita a l'Hamburger Bahnhof",
                    "Exploració de la Catedral Ortodoxa Russa",
                    "Passeig pel Barri de Neukölln",
                    "Visita al Museu de la Història Alemanya",
                    "Recorregut pel Parc Tempelhof",
                    "Passeig per la Plaça Karl-Marx",
                    "Visita a la Galeria d'Art C/O Berlin",
                    "Exploració del Cementiri de St. Matthäus",
                    "Passeig pel Barri de Charlottenburg",
                    "Visita al Museu de la RDA",
                    "Recorregut pel Parc Volkspark",
                    "Passeig per la Plaça Savignyplatz",
                    "Visita a l'Art Center Tacheles",
                    "Exploració de l'Antic Cementiri de St. Marien",
                    "Passeig pel Barri de Lichtenberg",
                    "Visita al Museu de la Bauhaus",
                    "Recorregut pel Parc Viktoriapark",
                    "Passeig per la Plaça Kastanienallee",
                    "Visita a la Galeria d'Art KW Institute",
                    "Exploració de l'Estació Central de Berlín",
                    "Passeig pel Barri de Moabit",
                    "Visita al Museu de la Resistència Alemanya",
                    "Recorregut pel Parc Treptower",
                    "Passeig per la Plaça Heinrichplatz",
                    "Visita a la Galeria d'Art Sammlung Boros",
                    "Exploració de l'Antic Cementiri de St. Nicholas",
                    "Passeig pel Barri de Kreuzberg",
                    "Visita al Museu del Cine de Berlín",
                    "Recorregut pel Parc Friedrichshain",
                    "Passeig per la Plaça Richardplatz",
                    "Visita a l'Hamburger Bahnhof",
                    "Exploració de la Catedral Ortodoxa Russa",
                    "Passeig pel Barri de Friedrichshain",
                    "Visita a una galeria d'art contemporani a Neukölln",
                    "Exploració del barri de moda de Prenzlauer Berg",
                    "Passeig per la plaça Karl-Marx-Allee a la nit",
                    "Visita a un club de música electrònica a Kreuzberg",
                    "Recorregut nocturn per la muralla de Berlín",
                    "Passeig pel barri de Mitte a la nit",
                    "Visita a un teatre de cabaret a Friedrichshain",
                    "Exploració del barri multicultural de Wedding",
                    "Passeig per la plaça Rosa Luxemburg a la nit",
                    "Visita a una galeria d'art contemporani a Kreuzberg",
                ],
                "nit": [
                    "Espectacle a l'Òpera Alemanya de Berlín",
                    "Cinema en un cine de l'antic Berlin Oriental",
                    "Visita al Planetari Zeiss Gross",
                    "Assistir a un concert a la Filharmònica de Berlín",
                    "Passeig nocturn per l'Alexanderplatz",
                    "Visita a un club de jazz a Kreuzberg",
                    "Recorregut nocturn per la ciutat en bicicleta",
                    "Passeig per la plaça de la Porta de Brandenburg il·luminada",
                    "Visita a un bar de còctels a Prenzlauer Berg",
                    "Exploració del barri alternatiu de Friedrichshain",
                    "Passeig per la plaça de Gendarmenmarkt a la nit",
                    "Visita a un cabaret a Mitte",
                    "Recorregut nocturn per la muralla de Berlín",
                    "Passeig pel barri de Neukölln a la nit",
                    "Visita a un teatre experimental a Wedding",
                    "Exploració del barri bohemi de Kreuzberg",
                    "Passeig per la plaça Rosa Luxemburg a la nit",
                    "Visita a un club de música electrònica a Mitte",
                    "Recorregut nocturn per el carrer Oranienstrasse",
                    "Passeig pel barri de Charlottenburg a la nit",
                    "Visita a una galeria d'art contemporani a Friedrichshain",
                    "Exploració del barri multicultural de Wedding",
                    "Passeig per la plaça de Potsdamer a la nit",
                    "Visita a un teatre de cabaret a Kreuzberg",
                    "Recorregut nocturn pel parc Tiergarten",
                    "Passeig pel barri de Schöneberg a la nit",
                    "Visita a un bar de música en directe a Neukölln",
                    "Exploració del barri històric de Mitte",
                    "Passeig per la plaça Bebelplatz a la nit",
                    "Visita a un club de techno a Friedrichshain",
                    "Recorregut nocturn per l'estació central de Berlín",
                    "Passeig pel barri de Prenzlauer Berg a la nit",
                    "Visita a un teatre experimental a Kreuzberg",
                    "Exploració del barri artístic de Charlottenburg",
                    "Passeig per la plaça Kollwitzplatz a la nit",
                    "Visita a un bar de còctels a Mitte",
                    "Recorregut nocturn per la plaça Hackescher Markt",
                    "Passeig pel barri de Friedrichshain a la nit",
                    "Visita a una galeria d'art contemporani a Neukölln",
                    "Exploració del barri de moda de Prenzlauer Berg",
                    "Passeig per la plaça Karl-Marx-Allee a la nit",
                    "Visita a un club de música electrònica a Kreuzberg",
                    "Recorregut nocturn per la muralla de Berlín",
                    "Passeig pel barri de Mitte a la nit",
                    "Visita a un teatre de cabaret a Friedrichshain",
                    "Exploració del barri multicultural de Wedding",
                    "Passeig per la plaça Rosa Luxemburg a la nit",
                    "Visita a una galeria d'art contemporani a Kreuzberg",
                    "Exploració del barri de moda de Prenzlauer Berg",
                    "Passeig per la plaça Karl-Marx-Allee a la nit",
                    "Visita a un club de música electrònica a Kreuzberg",
                    "Recorregut nocturn per la muralla de Berlín"
                ]
            },
            "ludica": {
                "mati": [
                    "Visitar el Museu de Pérgam",
                    "Explorar l'illa dels Museus",
                    "Passejar pel parc Tiergarten",
                    "Visitar el Memorial de l'Holocaust",
                    "Fer un recorregut en bicicleta per la ciutat",
                    "Visitar la Catedral de Berlín",
                    "Explorar el Mercat de Mauerpark",
                    "Fer un tour a peu pel mur de Berlín",
                    "Visitar el Museu DDR",
                    "Navegar pel riu Spree",
                    "Fer un pícnic al Viktoriapark",
                    "Visitar el Museu d'Història Natural",
                    "Explorar el barri de Kreuzberg",
                    "Passejar per la plaça Alexanderplatz",
                    "Visitar el Museu de Tecnologia",
                    "Fer un tour guiada pel Palau de Charlottenburg",
                    "Visitar el Jardí Zoològic de Berlín",
                    "Explorar el barri de Prenzlauer Berg",
                    "Passejar per la Unter den Linden",
                    "Visitar el Museu Bauhaus Archive",
                    "Fer un passeig en barca per la Bastanta",
                    "Visitar la Torre de la Televisió",
                    "Explorar el barri de Friedrichshain",
                    "Passejar pel mercat de Hackescher Hofe",
                    "Visitar el Museu de la RDA",
                    "Fer un recorregut pel parcs de Treptower",
                    "Visitar el Museu d'Història de Berlín",
                    "Explorar el barri de Mitte",
                    "Passejar per la East Side Gallery",
                    "Visitar el Museu de Belles Arts",
                    "Fer un tour pel Parlament de Berlín",
                    "Visitar el Museu Juïc de Berlín",
                    "Explorar el barri de Neukölln",
                    "Passejar pel carrer Kurfürstendamm",
                    "Visitar el Museu del Cinema",
                    "Fer un tour pel barri jueu de Berlín",
                    "Visitar el Museu d'Història Natural",
                    "Explorar el barri de Wedding",
                    "Passejar per la Gendarmenmarkt",
                    "Visitar el Museu de la Xocolata de Berlín",
                    "Fer un recorregut pel barri de Moabit",
                    "Visitar el Museu de les Comunicacions",
                    "Explorar el barri de Schöneberg",
                    "Passejar pel mercat de Winterfeldtplatz",
                    "Visitar el Museu de la Ciència",
                    "Fer un tour pels barris alternatius de Berlín",
                    "Visitar el Museu dels Aliats",
                    "Explorar el barri de Reinickendorf",
                    "Passejar pel parc Viktoriapark",
                    "Visitar el Museu de Fotografia de Berlín"
                ],
                "tarda": [
                    "Fer un tour en segway per la ciutat",
                    "Anar de compres a la Friedrichstraße",
                    "Visitar el Palau del Reichstag",
                    "Passejar pel barri de Charlottenburg",
                    "Fer un recorregut en bicicleta per Tempelhof",
                    "Anar de compres a KaDeWe",
                    "Visitar el barri de Nikolaiviertel",
                    "Passejar per la Plaça de Gendarmenmarkt",
                    "Fer un tour per la Berliner Unterwelten",
                    "Visitar el barri de Hackesche Höfe",
                    "Explorar el barri de Schöneberg",
                    "Visitar el Memorial del Muro de Berlín",
                    "Anar de compres a la Kurfürstendamm",
                    "Visitar la Catedral de Sant Hedwig",
                    "Passejar pel carrer Oranienstraße",
                    "Fer un recorregut pel carrer Unter den Linden",
                    "Anar de compres a Friedrichshain",
                    "Visitar l'Església dels 12 Apòstols",
                    "Passejar per la plaça Alexanderplatz",
                    "Fer un tour de cervesa artesana per la ciutat",
                    "Visitar la Galeria d'Art KW",
                    "Anar de compres a Potsdamer Platz",
                    "Visitar la Colònia Hutterite",
                    "Passejar pel carrer Karl-Marx-Allee",
                    "Fer un recorregut per la Berliner Dom",
                    "Anar de compres a Mitte",
                    "Visitar el barri de Kreuzberg",
                    "Passejar per la East Side Gallery",
                    "Fer un tour gastronòmic per Berlín",
                    "Visitar el Museu de Belles Arts",
                    "Anar de compres a Neukölln",
                    "Visitar la Torre de la Televisió",
                    "Passejar pel carrer Bergmannstraße",
                    "Fer un recorregut pel Muro de Berlín",
                    "Anar de compres a Wedding",
                    "Visitar la Colònia de l'Art Tacheles",
                    "Passejar pel mercat de Hackescher Hofe",
                    "Fer un tour per la comunitat artística de Berlín",
                    "Visitar el Jardí Zoològic de Berlín",
                    "Anar de compres a Schöneberg",
                    "Visitar el Museu Bauhaus Archive",
                    "Passejar per la Friedrichstraße",
                    "Fer un recorregut pel Parc Tiergarten",
                    "Anar de compres a Reinickendorf",
                    "Visitar el Museu dels Aliats",
                    "Passejar pel mercat de Winterfeldtplatz",
                    "Fer un tour de Street Art per la ciutat",
                    "Visitar el Palau de Charlottenburg",
                    "Passejar per la East Side Gallery",
                    "Fer un tour gastronòmic per Berlín",
                    "Visitar el Museu de Belles Arts",
                    "Anar de compres a Neukölln",
                    "Visitar la Torre de la Televisió",
                    "Passejar pel carrer Bergmannstraße",
                    "Fer un recorregut pel Muro de Berlín",
                ],
                "nit": [
                    "Anar a un concert a la Sala de la Filharmònica de Berlín",
                    "Provar la vida nocturna al barri de Friedrichshain",
                    "Assistir a una òpera a la Staatsoper Unter den Linden",
                    "Anar a un club de música electrònica a Kreuzberg",
                    "Gaudir d'una nit de jazz al bairro de Mitte",
                    "Explorar els bars de còctels a Prenzlauer Berg",
                    "Anar a una festa a la platja a Treptower Park",
                    "Assistir a un espectacle de dansa contemporània a Neukölln",
                    "Gaudir de la vida nocturna a Wedding",
                    "Anar a un bar de cervesa artesana a Schöneberg",
                    "Bailar en una festa temàtica a Charlottenburg",
                    "Assistir a un espectacle de teatre experimental a Reinickendorf",
                    "Gaudir d'una nit de salsa a KaDeWe",
                    "Anar a un club de música indie a Potsdamer Platz",
                    "Assistir a una projecció de cinema a l'aire lliure a Tiergarten",
                    "Explorar els bars clandestins a Mitte",
                    "Anar a un pub tradicional a Friedrichshain",
                    "Assistir a una obra de teatre al Teatre de l'Est",
                    "Gaudir d'una nit de karaoke a Neukölln",
                    "Anar a un bar de jazz a Prenzlauer Berg",
                    "Assistir a un espectacle de cabaret a Kreuzberg",
                    "Gaudir de la vida nocturna a Wedding",
                    "Anar a una festa de música en viu a Schöneberg",
                    "Bailar en una discoteca a Charlottenburg",
                    "Assistir a un concert de música clàssica a Reinickendorf",
                    "Gaudir d'una nit de música electrònica a Mitte",
                    "Anar a un bar de còctels a Friedrichshain",
                    "Assistir a un espectacle de dansa contemporània a Prenzlauer Berg",
                    "Gaudir de la vida nocturna a Neukölln",
                    "Anar a una festa a un bar en terrassa a Kreuzberg",
                    "Assistir a un espectacle de flamenc a Wedding",
                    "Bailar en una festa de reggae a Schöneberg",
                    "Gaudir d'una nit de música indie a Charlottenburg",
                    "Anar a un club de rock a Reinickendorf",
                    "Assistir a una projecció de cine experimental a Mitte",
                    "Gaudir de la vida nocturna a Friedrichshain",
                    "Anar a un bar de punk a Prenzlauer Berg",
                    "Assistir a un espectacle de màgia a Neukölln",
                    "Gaudir d'una nit de música en viu a Wedding",
                    "Anar a una festa de música hip-hop a Schöneberg",
                    "Bailar en una discoteca de techno a Charlottenburg",
                    "Assistir a un concert de música experimental a Reinickendorf",
                    "Gaudir d'una nit de música house a Mitte",
                    "Anar a un bar de música country a Friedrichshain",
                    "Assistir a un espectacle de dansa clàssica a Prenzlauer Berg",
                    "Gaudir de la vida nocturna a Neukölln",
                    "Gaudir de la vida nocturna a Wedding",
                    "Anar a un bar de cervesa artesana a Schöneberg",
                    "Bailar en una festa temàtica a Charlottenburg",
                    "Assistir a un espectacle de teatre experimental a Reinickendorf",
                    "Gaudir d'una nit de salsa a KaDeWe",
                    "Anar a un club de música indie a Potsdamer Platz",
                    "Assistir a una projecció de cinema a l'aire lliure a Tiergarten",
                    "Explorar els bars clandestins a Mitte",
                    "Anar a un pub tradicional a Friedrichshain",
                    "Assistir a una obra de teatre al Teatre de l'Est",
                    "Gaudir d'una nit de karaoke a Neukölln",
                ]
            },
            "festiva": {
                "mati": [
                    "Visitar el Museu de Pergamó",
                    "Passejar per l'illa dels Museus",
                    "Explorar el Palau de Charlottenburg",
                    "Fer un recorregut per la Puerta de Brandenburgo",
                    "Visitar el Muro de Berlín i el Memorial del Mur",
                    "Explorar el Reichstag",
                    "Fer un tour pel Berlín alternatiu a Kreuzberg",
                    "Passejar pel parc Tiergarten",
                    "Visitar la Catedral de Berlín",
                    "Explorar la Plaça Alexanderplatz",
                    "Anar al mercat de Mauerpark",
                    "Fer una visita a la Torre de la Televisió",
                    "Visitar el Mercat de Hackescher",
                    "Explorar el Jardí Zoològic de Berlín",
                    "Fer un tour per l'East Side Gallery",
                    "Passejar per la Karl-Marx-Allee",
                    "Anar de compres a la Friedrichstraße",
                    "Visitar el Museu del DDR",
                    "Fer un recorregut per la Topografia del Terror",
                    "Passejar per la Gendarmenmarkt",
                    "Explorar el Museu de la RDA",
                    "Fer una visita al Museu de la Torre de l'Escola de Nova Arquitectura",
                    "Passejar per la Kurfürstendamm",
                    "Visitar el Museu Juïc",
                    "Explorar la Galeria d'Art Contemporani Hamburger Bahnhof",
                    "Fer un recorregut per la Rotes Rathaus",
                    "Passejar per la Catedral de Santa Eduvigis",
                    "Anar de compres al Mercat de Winterfeldt",
                    "Visitar el Museu de Tecnologia",
                    "Explorar el Museu de la Història de Berlín",
                    "Fer una visita a l'Antiga Ópera de Berlín",
                    "Passejar per la Plaça Potsdamer",
                    "Visitar el Museu de l'Espia",
                    "Explorar la Plaça Rosa Luxemburg",
                    "Fer un recorregut pel Parc Viktoriapark",
                    "Passejar per la Galeria Lafayette",
                    "Anar de compres al Mercat de Bode",
                    "Visitar el Museu del Llibre de Berlín",
                    "Explorar el Museu d'Art Modern KW",
                    "Fer una visita a la Catedral de Sant Nicolau",
                    "Passejar per la Plaça de Bebel",
                    "Visitar el Museu dels Aliats",
                    "Explorar el Monument a la Batalla de Nació",
                    "Fer un recorregut pel Memorial de l'Holocaust",
                    "Passejar per la Plaça de Kollwitz",
                    "Anar de compres al Mercat de Boxhagener",
                    "Visitar el Museu de Cera de Berlín",
                    "Explorar el Museu de la Comunicació",
                    "Fer una visita al Museu de la Vida GDR",
                    "Passejar per la Biblioteca Central de Berlin"
                ],
                "tarda": [
                    "Visitar la Galeria d'Art de Berlin",
                    "Passejar pel parc de Treptower",
                    "Explorar la Font de Neptú",
                    "Fer un recorregut pel Parc Natural de Grunewald",
                    "Visitar el Museu de l'Espionatge",
                    "Explorar el Parc de Potsdam",
                    "Fer una visita a la Casa de la Conferència de Wannsee",
                    "Passejar per la Plaça de la Catedral",
                    "Visitar el Museu de la Múscia",
                    "Explorar el Museu de la Stasi",
                    "Fer un recorregut pel Memorial dels Juïfs Assassinats d'Europa",
                    "Passejar pel Jardí Botànic",
                    "Anar de compres al Mercat d'Antiguitats de Berlín",
                    "Visitar el Museu de la Pintura Mural",
                    "Explorar el Museu de Tecnologia de la Ciutat de Berlín",
                    "Fer una visita al Museu de la Resistència Alemanya",
                    "Passejar per la Plaça de la República",
                    "Visitar el Museu d'Història Militar",
                    "Explorar el Memorial a la Divisió de Berlín",
                    "Fer un recorregut pel Museu d'Història de la Medicina",
                    "Passejar pel Jardí Britànic de Berlín",
                    "Anar de compres al Mercat de Charlottenburg",
                    "Visitar el Museu de l'Il·lustració",
                    "Explorar el Museu de la Imatge en Moviment",
                    "Fer una visita al Museu dels Transport Públics",
                    "Passejar per la Plaça d'Oper",
                    "Visitar el Museu del Cinema",
                    "Explorar el Museu de la Història de l'Art",
                    "Fer un recorregut pel Memorial de les Brigades Internacionals",
                    "Passejar pel Parc de Friedrichshain",
                    "Anar de compres al Mercat de Moabit",
                    "Visitar el Museu de la Farmàcia",
                    "Explorar el Museu de l'Arquitectura",
                    "Fer una visita al Museu de l'Antiguitat",
                    "Passejar per la Plaça de Gendarmen",
                    "Visitar el Museu de l'Arxiu de Cinema",
                    "Explorar el Museu de la Botànica",
                    "Fer un recorregut pel Museu de la Història de la Premsa",
                    "Passejar pel Jardí Japonès de Berlín",
                    "Anar de compres al Mercat de Karl-August",
                    "Visitar el Museu de la Prehistòria",
                    "Explorar el Museu de la Fotografia",
                    "Fer una visita al Museu de la Màgia i l'Espectacle",
                    "Passejar per la Plaça de Schloss",
                    "Anar de compres al Mercat de La Savigny",
                    "Visitar el Museu de l'Electricitat",
                    "Explorar el Museu de la Marxa",
                    "Fer un recorregut pel Memorial de l'Aviació de Berlin",
                    "Anar de compres al Mercat de Charlottenburg",
                    "Visitar el Museu de l'Il·lustració",
                    "Explorar el Museu de la Imatge en Moviment",
                    "Fer una visita al Museu dels Transport Públics",
                    "Passejar per la Plaça d'Oper",
                    "Visitar el Museu del Cinema",
                    "Explorar el Museu de la Història de l'Art"
                ],
                "nit": [
                    "Assistir a un concert a la Berliner Philharmonie",
                    "Gaudir d'una obra de teatre al Teatre de Berlin",
                    "Anar a un club de música electrònica com el Berghain",
                    "Experimentar la vida nocturna a Kreuzberg",
                    "Assistir a un espectacle de cabaret al Bar jeder Vernunft",
                    "Gaudir d'un concert de música indie a la sala Lido",
                    "Anar a un bar de còctels a la zona de Mitte",
                    "Assistir a un espectacle de dansa contemporània al Volksbühne",
                    "Gaudir d'una nit de jazz al A-Trane",
                    "Anar a un club de salsa i ballar fins a l'hora matinera",
                    "Assistir a un espectacle de comèdia a la sala Comedy Club Kookaburra",
                    "Gaudir d'un concert de música clàssica a la Filharmònica de Berlin",
                    "Anar a un pub irlandès i gaudir d'un concert en viu",
                    "Assistir a una òpera al Staatsoper Unter den Linden",
                    "Gaudir d'un espectacle de flamenc al Peacock Berlin",
                    "Anar a un bar de vins i tastar vins alemanys",
                    "Assistir a un espectacle de circ al Chamäleon Theater",
                    "Gaudir d'una nit de música en viu al Quasimodo",
                    "Anar a un club de reggae i ballar fins a l'alba",
                    "Assistir a un espectacle de teatre experimental al Hebbel am Ufer",
                    "Gaudir d'un concert de música electrònica en un club subterrani",
                    "Anar a un bar de rock i gaudir de música en viu",
                    "Assistir a un espectacle de música folk a la sala Grüner Salon",
                    "Gaudir d'una nit de música hip-hop a la sala Yaam",
                    "Anar a un bar de cocktails temàtic i provar creacions úniques",
                    "Assistir a un espectacle de música clàssica a la Sala de Concerts Konzerthaus",
                    "Gaudir d'un concert de música indie a la sala Bi Nuu",
                    "Anar a un bar de blues i gaudir d'un concert en viu",
                    "Assistir a una actuació de flamenco a la sala Casa de España",
                    "Gaudir d'una nit de música techno a la sala Watergate",
                    "Anar a un club de música en viu i ballar al ritme de la música",
                    "Assistir a un espectacle de comèdia a la sala Quatsch Comedy Club",
                    "Gaudir d'un concert de jazz al A-Trane",
                    "Anar a un bar de música en directe i descobrir nous talents",
                    "Assistir a una representació de dansa contemporània al Radialsystem V",
                    "Gaudir d'una nit de música electrònica a la sala Ritter Butzke",
                    "Anar a un pub irlandès i gaudir d'una nit de música celta",
                    "Assistir a un espectacle de circ al Chamäleon Theater",
                    "Gaudir d'un concert de música en viu al White Trash Fast Food",
                    "Anar a un bar de vins i degustar vins internacionals",
                    "Assistir a un espectacle de teatre experimental al Ballhaus Ost",
                    "Gaudir d'una nit de música indie a la sala Lido",
                    "Anar a un club de salsa i ballar fins a l'alba",
                    "Assistir a un espectacle de comèdia a la sala Comedy Club Kookaburra",
                    "Gaudir d'un concert de música clàssica a la Filharmònica de Berlin",
                    "Assistir a una òpera al Staatsoper Unter den Linden",
                    "Gaudir d'un espectacle de flamenc al Peacock Berlin",
                    "Anar a un bar de vins i tastar vins alemanys",
                    "Assistir a un espectacle de circ al Chamäleon Theater",
                    "Gaudir d'una nit de música en viu al Quasimodo",
                    "Anar a un club de reggae i ballar fins a l'alba",
                    "Assistir a un espectacle de teatre experimental al Hebbel am Ufer"
                ]
            }
        }
    }

    for ciutat in ciutats:
        for tipus in tipusActivitats:
            for franja in franges:
                i = 0
                while i < 50:
                    activitat = URIRef('activitat' + ciutat + tipus + franja + str(i))
                    gr.add((activitat, RDF.type, PANT.Activitat))
                    gr.add((activitat, PANT.nom, Literal(activitats[ciutat][tipus][franja][i])))
                    gr.add((activitat, PANT.tipus, Literal(tipus)))
                    gr.add((activitat, PANT.franja, Literal(franja)))
                    gr.add((activitat, PANT.teCiutat, URIRef(ciutatsObj[ciutat])))

                    i += 1

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
