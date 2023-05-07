"""
.. module:: ontologies/Viatget

 Translated by owl2rdflib

 Translated to RDFlib from ontology urn:webprotege:ontology:f284b032-799d-4c40-8f60-a429799ce267

 :Date 07/05/2023 11:15:31
"""
from rdflib import URIRef
from rdflib.namespace import ClosedNamespace

PANT =  ClosedNamespace(
    uri=URIRef('urn:webprotege:ontology:f284b032-799d-4c40-8f60-a429799ce267'),
    terms=[
        # Classes
        'Ciutat',
        'DemanarViatge',
        'PaquetTancat',
        'R79kFHXLHEItDb8KIeVk0uU',
        'Allotjament',
        'CompanyiaTransport',
        'ObtenirAllotjaments',
        'Paquet',
        'PossiblesAllotjaments',
        'Resposta',
        'Transport',

        # Object properties
        'informaDelPaquet',
        'deCiutat',
        'deLaCompanyia',
        'ofereix',
        'teAllotjament',
        'teCiutat',
        'teComAPuntFinal',
        'teComAPuntInici',
        'teTransport',

        # Data properties
        'centric',
        'data',
        'dataFi',
        'dataInici',
        'pressupost',
        'preu',
        'tipus',
        'allotjamentC%C3%A8ntric'

        # Named Individuals
    ]
)
