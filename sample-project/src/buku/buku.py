class Buku:
    _idBuku = 0
    _judulBuku = ""
    _status_buku = ""
    _total_halaman = 0

    def __init__(self, idBuku, judulBuku, statusBuku, totalHalaman) -> None:
        self._idBuku = idBuku
        self._judulBuku = judulBuku
        self._status_buku = statusBuku
        self._total_halaman = totalHalaman
        

    def get_idBuku(self) :
        return self._idBuku
    
    def get_judulBuku(self) :
        return self._judulBuku
    
    def get_status_buku(self) :
        return self._status_buku
    
    def get_total_halaman(self) :
        return self._total_halaman
    
    def set_idBuku(self, idBuku) :
        self._idBuku = idBuku

    def set_judulBuku(self, judulBuku) :
        self._judulBuku = judulBuku

    def set_status_buku(self, statusBuku) :
        self._status_buku = statusBuku

    def set_totalHalaman(self, totalHalaman) :
        self._total_halaman = totalHalaman

    def __eq__(self, value: object) -> bool:

        if (not isinstance(value, Buku)) :
            return False
        
        res = self.get_judulBuku() == value.get_judulBuku()
        res = res and self.get_status_buku() == value.get_status_buku()
        res = res and self.get_total_halaman() == value.get_total_halaman()
        return res
    
    def delete_by_id(self, id) :
        query = "DELETE FROM buku WHERE id_buku = ?"
        self._cursor.execute(query, (id,))
        self._conn.commit()