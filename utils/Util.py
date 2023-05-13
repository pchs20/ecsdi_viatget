"""
.. module:: Util.py

Util.py
******

:Description: Util.py

    Different Auxiliary functions used for different purposes

:Authors:
    bejar

:Version: 

:Date:  23/02/2021
"""
import socket
from pif import get_public_ip
from rdflib import Graph, Literal
from rdflib.namespace import RDF, FOAF
from utils.ACLMessages import send_message, build_message
from utils.OntoNamespaces import Namespace
from ontologies.ACL import ACL
from ontologies.DSO import DSO
from utils.Logging import config_logger

agn = Namespace("http://www.agentes.org#")
logger = config_logger(level=1)


def gethostname():
    try:
        return socket.gethostbyaddr(get_public_ip())[0]
    except:
        return socket.gethostname()


# Funció que registra un agent al servei directori indicat
# Extraiem la part comuna de la funció register_message de qualsevol agent
def registrar_agent(agent, directori, tipus, mss_cnt):
    gmess = Graph()

    # Construimos el mensaje de registro
    gmess.bind('foaf', FOAF)
    gmess.bind('dso', DSO)
    reg_obj = agn[agent.name + '-Register']
    gmess.add((reg_obj, RDF.type, DSO.Register))
    gmess.add((reg_obj, DSO.Uri, agent.uri))
    gmess.add((reg_obj, FOAF.name, Literal(agent.name)))
    gmess.add((reg_obj, DSO.Address, Literal(agent.address)))
    gmess.add((reg_obj, DSO.AgentType, tipus))

    # Lo metemos en un envoltorio FIPA-ACL y lo enviamos
    return send_message(
        build_message(gmess, perf=ACL.request,
                      sender=agent.uri,
                      receiver=directori.uri,
                      content=reg_obj,
                      msgcnt=mss_cnt),
        directori.address)


def directory_search_message(emisor, directori, type, mss_cnt):
    """
    Busca en el servicio de registro mandando un
    mensaje de request con una accion Seach del servicio de directorio

    Podria ser mas adecuado mandar un query-ref y una descripcion de registo
    con variables

    :param type:
    :return:
    """
    logger.info('Buscamos en el servicio de registro')

    gmess = Graph()

    gmess.bind('foaf', FOAF)
    gmess.bind('dso', DSO)
    reg_obj = agn[emisor.name + '-search']
    gmess.add((reg_obj, RDF.type, DSO.Search))
    gmess.add((reg_obj, DSO.AgentType, type))

    msg = build_message(gmess, perf=ACL.request,
                        sender=emisor.uri,
                        receiver=directori.uri,
                        content=reg_obj,
                        msgcnt=mss_cnt)
    gr = send_message(msg, directori.address)
    mss_cnt += 1
    logger.info('Recibimos informacion del agente')

    return gr


# Inicialitzem un agent amb el que ens retorna l'agent directori, en demanar-li per un agent d'un tipus concret
def aconseguir_agent(emisor, agent, directori, tipus, mss_cnt):
    # Buscamos en el directorio un agente de tipo tipus
    gr = directory_search_message(emisor, directori, tipus, mss_cnt)

    # Obtenemos la direccion del agente de la respuesta
    # No hacemos ninguna comprobacion sobre si es un mensaje valido
    msg = gr.value(predicate=RDF.type, object=ACL.FipaAclMessage)
    content = gr.value(subject=msg, predicate=ACL.content)
    agent.address = gr.value(subject=content, predicate=DSO.Address)
    agent.uri = gr.value(subject=content, predicate=DSO.Uri)
