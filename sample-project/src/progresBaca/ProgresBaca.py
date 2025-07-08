import datetime

class ProgresBaca:

    id_buku = ""
    tanggal_mulai = datetime.datetime.now()
    halaman_sekarang = 0
    pembacaan_ke = 0

    def __init__(self, id_buku, pembacaan_ke, halaman_sekarang, tanggal_mulai):
        self.id_buku = id_buku
        self.tanggal_mulai = tanggal_mulai
        self.halaman_sekarang = halaman_sekarang
        self.pembacaan_ke = pembacaan_ke

    def get_idBuku(self) -> int:
        return self.id_buku
    
    def set_idBuku(self, id : int) -> int:
        self.id_buku = id
    
    def getTanggalMulai(self) -> datetime:
        return self.tanggal_mulai
    
    def setTanggalMulai(self, date):
        self.tanggal_mulai = date

    def getPenghitungHari(self) -> int:
        date_difference = datetime.datetime.now() - self.tanggal_mulai

        days_difference = date_difference.days
        return days_difference
    
    def setPenghitungHari(self, hari):
        self = hari
    
    def getHalamanSekarang(self) -> int:
        return self.halaman_sekarang
    
    def setHalamanSementara(self, halaman):
        self.halaman_sekarang = halaman
    
    def getPembacaanKe(self) -> int:
        return self.pembacaan_ke
    
    def setPembacaanKe(self, pembacaanKe):
        self.pembacaan_ke = pembacaanKe
