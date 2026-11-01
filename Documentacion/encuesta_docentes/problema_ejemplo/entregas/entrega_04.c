#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <ctype.h>

/*
 * Ova funkcija prima niz znakova (string) i jedan ceo broj.
 * Ona prolazi kroz string i svaki put kada naidje na jedan ili vise
 * uzastopnih razmaka (prazan prostor), umesto tih razmaka ubacuje
 * dati broj (pretvoren u niz cifara). Na taj nacin se zadrzava
 * originalna struktura teksta â€“ reci ostaju na istom mestu, samo se
 * razmaci zamenjuju brojem. Funkcija vraca novi string koji je
 * dinamicki alociran, pa ga korisnik mora osloboditi nakon upotrebe.
 */
char* ubaciBrojUPrazanProstor(const char* ulaz, int broj) {
    // Prvo proveravamo da li je ulazni string prazan ili NULL
    if (ulaz == NULL) {
        return NULL;
    }

    // Pretvaramo ceo broj u niz znakova (string) pomocu sprintf
    char brojString[12]; // dovoljno za najveci int (ukljucujuci i minus)
    sprintf(brojString, "%d", broj);
    int duzinaBroja = strlen(brojString);

    // Sada prolazimo kroz ulazni string da izbrojimo koliko ima
    // sekvenci razmaka i koliko ukupno razmaka ima.
    int i = 0;
    int brojSekvenci = 0;
    int ukupnoRazmaka = 0;

    while (ulaz[i] != '\0') {
        if (ulaz[i] == ' ') { // naisli smo na razmak
            brojSekvenci++; // nova sekvenca razmaka
            // brojimo sve uzastopne razmake
            while (ulaz[i] == ' ') {
                ukupnoRazmaka++;
                i++;
            }
        } else {
            i++; // nije razmak, samo idemo dalje
        }
    }

    // Racunamo koliko ce karaktera imati novi string:
    // duzina originala - svi razmaci + (broj sekvenci * duzina broja)
    int duzinaOriginala = strlen(ulaz);
    int duzinaRezultata = duzinaOriginala - ukupnoRazmaka + (brojSekvenci * duzinaBroja);

    // Alociramo memoriju za novi string (plus jedan za '\0')
    char* rezultat = (char*)malloc(duzinaRezultata + 1);
    if (rezultat == NULL) {
        // Ako alokacija ne uspe, vracamo NULL
        return NULL;
    }

    // Sada drugi prolazak: kopiramo karaktere iz originala u rezultat,
    // ali kada naidjemo na razmak, umesto njega ubacujemo broj
    int j = 0; // indeks u rezultatu
    i = 0;     // indeks u originalu

    while (ulaz[i] != '\0') {
        if (ulaz[i] == ' ') {
            // Na mesto sekvence razmaka upisujemo broj
            strcpy(rezultat + j, brojString);
            j += duzinaBroja;
            // Preskacemo sve razmake u ovoj sekvenci
            while (ulaz[i] == ' ') {
                i++;
            }
        } else {
            // Ako nije razmak, samo kopiramo karakter
            rezultat[j] = ulaz[i];
            j++;
            i++;
        }
    }

    // Postavljamo kraj stringa
    rezultat[j] = '\0';

    // Vracamo pokazivac na novi string
    return rezultat;
}

/*
 * Glavni program sluzi za testiranje funkcije.
 * Korisnik unosi string i broj, a program ispisuje rezultat.
 */
int main() {
    // Testiramo sa nekoliko primera
    printf("Testiranje funkcije 'ubaciBrojUPrazanProstor':\n\n");

    // Prvi test: obican tekst sa razmacima
    char test1[] = "Danas je lep dan";
    int broj1 = 5;
    char* rez1 = ubaciBrojUPrazanProstor(test1, broj1);
    if (rez1 != NULL) {
        printf("Original: \"%s\"\n", test1);
        printf("Broj: %d\n", broj1);
        printf("Rezultat: \"%s\"\n\n", rez1);
        free(rez1); // oslobadjamo memoriju
    }

    // Drugi test: vise uzastopnih razmaka
    char test2[] = "abc   def   ghi";
    int broj2 = 123;
    char* rez2 = ubaciBrojUPrazanProstor(test2, broj2);
    if (rez2 != NULL) {
        printf("Original: \"%s\"\n", test2);
        printf("Broj: %d\n", broj2);
        printf("Rezultat: \"%s\"\n\n", rez2);
        free(rez2);
    }

    // Treci test: razmaci na pocetku i kraju
    char test3[] = "   voda   ";
    int broj3 = -7;
    char* rez3 = ubaciBrojUPrazanProstor(test3, broj3);
    if (rez3 != NULL) {
        printf("Original: \"%s\"\n", test3);
        printf("Broj: %d\n", broj3);
        printf("Rezultat: \"%s\"\n\n", rez3);
        free(rez3);
    }

    // Cetvrti test: nema razmaka
    char test4[] = "NemaRazmaka";
    int broj4 = 0;
    char* rez4 = ubaciBrojUPrazanProstor(test4, broj4);
    if (rez4 != NULL) {
        printf("Original: \"%s\"\n", test4);
        printf("Broj: %d\n", broj4);
        printf("Rezultat: \"%s\"\n\n", rez4);
        free(rez4);
    }

    // Peti test: prazan string
    char test5[] = "";
    int broj5 = 42;
    char* rez5 = ubaciBrojUPrazanProstor(test5, broj5);
    if (rez5 != NULL) {
        printf("Original: \"%s\"\n", test5);
        printf("Broj: %d\n", broj5);
        printf("Rezultat: \"%s\"\n\n", rez5);
        free(rez5);
    }

    printf("Kraj testiranja.\n");
    return 0;
}