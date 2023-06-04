"""
.. module:: ontologies/Viatget

 Translated by owl2rdflib

 Translated to RDFlib from ontology https://ontologia.org#

 :Date 04/06/2023 18:32:31
"""
from rdflib import URIRef
from rdflib.namespace import ClosedNamespace

PANT =  ClosedNamespace(
    uri=URIRef('https://ontologia.org#'),
    terms=[
        # Classes
        'Activitat',
        'Ciutat',
        'ComprovantPagament',
        'DemanarViatge',
        'ObtenirActivitats',
        'ObtenirTransports',
        'Pagar',
        'PaquetTancat',
        'PossiblesActivitats',
        'PossiblesTransports',
        'R79kFHXLHEItDb8KIeVk0uU',
        'RealitzarPagament',
        'Transo',
        'ValidacioPagament',
        'Allotjament',
        'CompanyiaTransport',
        'ObtenirAllotjaments',
        'Paquet',
        'PossiblesAllotjaments',
        'Resposta',
        'Transport',

        # Object properties
        'informaDelPaquet',
        'teTransportAnada',
        'teTransportTornada',
        'deCiutat',
        'deLaCompanyia',
        'ofereix',
        'teAllotjament',
        'teCiutat',
        'teComAPuntFinal',
        'teComAPuntInici',

        # Data properties
        'activitatsQuantCulturals',
        'activitatsQuantFestives',
        'activitatsQuantLudiques',
        'franja',
        'nom',
        'numeroTargeta',
        'preuMaxim',
        'tipusTargeta',
        'centric',
        'data',
        'dataFi',
        'dataInici',
        'pressupost',
        'preu',
        'tipus',
        'allotjamentCentric'

        # Named Individuals
    ]
)
