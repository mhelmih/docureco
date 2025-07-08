class Catatan:

    _idCatatan = 0
    _idBuku = 0
    _halamanBuku = 0
    _kontenCatatan = ""


    def __init__(self,idCatatan,idBuku,halamanBuku,kontenCatatan):
        self._idCatatan = idCatatan
        self._idBuku = idBuku
        self._halamanBuku = halamanBuku
        self._kontenCatatan = kontenCatatan

    def get_idCatatan(self):
        return self._idCatatan
    
    def get_idBuku(self):
        return self._idBuku
    
    def get_halamanBuku(self):
        return self._halamanBuku
    
    def get_kontenCatatan(self):
        return self._kontenCatatan
    
    def set_idCatatan(self,idCatatan):
        self._idCatatan = idCatatan

    def set_idBuku(self,idBuku):
        self._idBuku = idBuku

    def set_halamanBuku(self,halamanBuku):
        self._halamanBuku = halamanBuku

    def set_kontenCatatan(self,kontenCatatan):
        self._kontenCatatan = kontenCatatan

    def __eq__(self,other) -> bool:
        if not isinstance(other, Catatan) :
            return False

        return self.get_idCatatan() == other.get_idCatatan() and self.get_idBuku() == other.get_idBuku() and self.get_halamanBuku() == other.get_halamanBuku() and self.get_kontenCatatan() == other.get_kontenCatatan()