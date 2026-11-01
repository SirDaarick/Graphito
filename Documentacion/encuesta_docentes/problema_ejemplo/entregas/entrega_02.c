#include <stdio.h>
#include <stdlib.h>
char *v1(char *v2, int v3)
{
	char *v4 = v2;
	int v5 = 0;
	int v6 = 0;
	int v7 = v3;
	if(v7<0) v5 = v5+1;
	v7 = abs(v7);
	while(v7 != 0) {
		v7/=10;
		v5++;
	}
	while(*v4==' ' && *v4!='\0') v4++;
	while(*v4!= '\0') {
		while(*v4!=' ' && *v4!='\0') {
			v4++;
		}
		char *v8=v4;
		while(*v8 == ' ' && *v8!= '\0')  {
			v8++;
			v6=1;
		}
		if(*v8!='\0') {
			char * v9=v4;
			while(*v9!='\0') v9++;
			while(v9 > v4) {
				*(v9 + v5+1) = *v9;
				v9--;
			}
			v4++;
			char *v10 = v4 + v5 ;
			v7 = v3;
			if(v6==1) {
				*v10 =  ' ';
				v10 --;
			}
			while(v7!=0) {
				*v10=v7%10 +'0';
				v7/=10;
				v10--;
			}
		} else break;
		while(*v4>= '0' && *v4<='9' && *v4!='\0') v4++;
		while(*v4== ' ' && *v4!='\0') v4++;
	}
	return v2;
}
int main()
{
	return 0;
}
