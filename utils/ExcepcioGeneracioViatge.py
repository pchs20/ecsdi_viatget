
class ExcepcioGeneracioViatge(Exception):
    def __init__(self, motiu="No s'ha pogut generar el teu pla!"):
        self.motiu = motiu
        super().__init__(self.motiu)
