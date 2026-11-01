#include <stdio.h>
#include <string.h>

void ubaciBrojUPrazneProstore(char *nizZnakova, int broj) {
    char brojStr[20];
    sprintf(brojStr, "%d", broj);
    int brojDuzine = strlen(brojStr);
    char temp[1024];
    int tempIndex = 0;
    int i = 0;
    while (nizZnakova[i] != '\0') {
        if (nizZnakova[i] == ' ') {
            int j = i;
            while (nizZnakova[j] == ' ') {
                j++;
            }
            strcpy(temp + tempIndex, brojStr);
            tempIndex += brojDuzine;
            i = j;
        } else {
            temp[tempIndex++] = nizZnakova[i++];
        }
    }
    temp[tempIndex] = '\0';
    strcpy(nizZnakova, temp);
}