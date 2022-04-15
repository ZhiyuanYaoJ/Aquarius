/*
 * header.c
 *
 *
 *      some of the code is from site BinaryTides, written by Silver Moon
 */

#include<sys/socket.h>
#include<arpa/inet.h>
#include<stdio.h>
#include<string.h>

#include "header.h"


void print_ethernet_header(const u_char *Buffer, int Size)
{
    struct ethhdr *eth = (struct ethhdr *)Buffer;

    printf( "\n");
    printf( "Ethernet Header\n");
    printf( "   |-Destination Address : %.2X-%.2X-%.2X-%.2X-%.2X-%.2X \n", eth->h_dest[0] , eth->h_dest[1] , eth->h_dest[2] , eth->h_dest[3] , eth->h_dest[4] , eth->h_dest[5] );
    printf( "   |-Source Address      : %.2X-%.2X-%.2X-%.2X-%.2X-%.2X \n", eth->h_source[0] , eth->h_source[1] , eth->h_source[2] , eth->h_source[3] , eth->h_source[4] , eth->h_source[5] );
    printf( "   |-Protocol            : %u \n",(unsigned short)eth->h_proto);
}

void print_ip_header(const u_char * Buffer, int Size)
{
    print_ethernet_header(Buffer , Size);

    unsigned short iphdrlen;

    struct iphdr *iph = (struct iphdr *)(Buffer  + sizeof(struct ethhdr) );
    iphdrlen =iph->ihl*4;

    memset(&source, 0, sizeof(source));
    source.sin_addr.s_addr = iph->saddr;

    memset(&dest, 0, sizeof(dest));
    dest.sin_addr.s_addr = iph->daddr;

    printf( "\n");
    printf( "IP Header\n");
    printf( "   |-IP Version        : %d\n",(unsigned int)iph->version);
    printf( "   |-IP Header Length  : %d DWORDS or %d Bytes\n",(unsigned int)iph->ihl,((unsigned int)(iph->ihl))*4);
    printf( "   |-Type Of Service   : %d\n",(unsigned int)iph->tos);
    printf( "   |-IP Total Length   : %d  Bytes(Size of Packet)\n",ntohs(iph->tot_len));
    printf( "   |-Identification    : %d\n",ntohs(iph->id));
    //printf( "   |-Reserved ZERO Field   : %d\n",(unsigned int)iphdr->ip_reserved_zero);
    //printf( "   |-Dont Fragment Field   : %d\n",(unsigned int)iphdr->ip_dont_fragment);
    //printf( "   |-More Fragment Field   : %d\n",(unsigned int)iphdr->ip_more_fragment);
    printf( "   |-TTL      : %d\n",(unsigned int)iph->ttl);
    printf( "   |-Protocol : %d\n",(unsigned int)iph->protocol);
    printf( "   |-Checksum : %d\n",ntohs(iph->check));
    printf( "   |-Source IP        : %s\n" , inet_ntoa(source.sin_addr) );
    printf( "   |-Destination IP   : %s\n" , inet_ntoa(dest.sin_addr) );
}

void print_tcp_packet(const u_char * Buffer, int Size, FILE *fptr)
{
    unsigned short iphdrlen;

    struct iphdr *iph = (struct iphdr *)( Buffer  + sizeof(struct ethhdr) );
    iphdrlen = iph->ihl*4;

    struct tcphdr *tcph=(struct tcphdr*)(Buffer + iphdrlen + sizeof(struct ethhdr));

    int header_size =  sizeof(struct ethhdr) + iphdrlen + tcph->doff*4;

    // printf( "\n\n***********************TCP Packet*************************\n");

    // print_ip_header(Buffer,Size);

    // printf( "\n");
    // printf( "TCP Header\n");
    // printf( "   |-Source Port      : %u\n",ntohs(tcph->source));
    // printf( "   |-Destination Port : %u\n",ntohs(tcph->dest));
    // printf( "   |-Sequence Number    : %u\n",ntohl(tcph->seq));
    // printf( "   |-Acknowledge Number : %u\n",ntohl(tcph->ack_seq));
    // printf( "   |-Header Length      : %d DWORDS or %d BYTES\n" ,(unsigned int)tcph->doff,(unsigned int)tcph->doff*4);
    //printf( "   |-CWR Flag : %d\n",(unsigned int)tcph->cwr);
    //printf( "   |-ECN Flag : %d\n",(unsigned int)tcph->ece);
    // printf( "   |-Urgent Flag          : %d\n",(unsigned int)tcph->urg);
    if ((unsigned int)tcph->ack > 0) {
        fprintf(fptr, "data\n");
    }
    else if ((unsigned int)tcph->syn > 0) {
        fprintf(fptr, "first\n");
    }

    // printf( "ack : %d\n",(unsigned int)tcph->ack);
    // printf( "   |-Push Flag            : %d\n",(unsigned int)tcph->psh);
    // printf( "   |-Reset Flag           : %d\n",(unsigned int)tcph->rst);
    // printf( "   |-Synchronise Flag     : %d\n",(unsigned int)tcph->syn);
    // printf( "   |-Finish Flag          : %d\n",(unsigned int)tcph->fin);
    // printf( "   |-Window         : %d\n",ntohs(tcph->window));
    // printf( "   |-Checksum       : %d\n",ntohs(tcph->check));
    // printf( "   |-Urgent Pointer : %d\n",tcph->urg_ptr);
    // printf( "\n");
    // printf( "                        DATA Dump                         ");
    // printf( "\n");

    // printf( "IP Header\n");
    // PrintData(Buffer,iphdrlen);

    // printf( "TCP Header\n");
    // PrintData(Buffer+iphdrlen,tcph->doff*4);

    // printf( "Data Payload\n");
    // PrintData(Buffer + header_size , Size - header_size );

    // printf( "\n###########################################################");
}

void print_udp_packet(const u_char *Buffer , int Size)
{

    unsigned short iphdrlen;

    struct iphdr *iph = (struct iphdr *)(Buffer +  sizeof(struct ethhdr));
    iphdrlen = iph->ihl*4;

    struct udphdr *udph = (struct udphdr*)(Buffer + iphdrlen  + sizeof(struct ethhdr));

    int header_size =  sizeof(struct ethhdr) + iphdrlen + sizeof udph;

    printf( "\n\n***********************UDP Packet*************************\n");

    print_ip_header(Buffer,Size);

    printf( "\nUDP Header\n");
    printf( "   |-Source Port      : %d\n" , ntohs(udph->source));
    printf( "   |-Destination Port : %d\n" , ntohs(udph->dest));
    printf( "   |-UDP Length       : %d\n" , ntohs(udph->len));
    printf( "   |-UDP Checksum     : %d\n" , ntohs(udph->check));

    printf( "\n");
    printf( "IP Header\n");
    PrintData(Buffer , iphdrlen);

    printf( "UDP Header\n");
    PrintData(Buffer+iphdrlen , sizeof udph);

    printf( "Data Payload\n");

    //Move the pointer ahead and reduce the size of string
    PrintData(Buffer + header_size , Size - header_size);

    printf( "\n###########################################################");
}

void print_icmp_packet(const u_char * Buffer , int Size)
{
    unsigned short iphdrlen;

    struct iphdr *iph = (struct iphdr *)(Buffer  + sizeof(struct ethhdr));
    iphdrlen = iph->ihl * 4;

    struct icmphdr *icmph = (struct icmphdr *)(Buffer + iphdrlen  + sizeof(struct ethhdr));

    int header_size =  sizeof(struct ethhdr) + iphdrlen + sizeof icmph;

    printf( "\n\n***********************ICMP Packet*************************\n");

    print_ip_header(Buffer , Size);

    printf( "\n");

    printf( "ICMP Header\n");
    printf( "   |-Type : %d",(unsigned int)(icmph->type));

    if((unsigned int)(icmph->type) == 11)
    {
        printf( "  (TTL Expired)\n");
    }
    else if((unsigned int)(icmph->type) == ICMP_ECHOREPLY)
    {
        printf( "  (ICMP Echo Reply)\n");
    }

    printf( "   |-Code : %d\n",(unsigned int)(icmph->code));
    printf( "   |-Checksum : %d\n",ntohs(icmph->checksum));
    //printf( "   |-ID       : %d\n",ntohs(icmph->id));
    //printf( "   |-Sequence : %d\n",ntohs(icmph->sequence));
    printf( "\n");

    printf( "IP Header\n");
    PrintData(Buffer,iphdrlen);

    printf( "UDP Header\n");
    PrintData(Buffer + iphdrlen , sizeof icmph);

    printf( "Data Payload\n");

    //Move the pointer ahead and reduce the size of string
    PrintData(Buffer + header_size , (Size - header_size) );

    printf( "\n###########################################################");
}

void PrintData (const u_char * data , int Size)
{
    int i , j;
    for(i=0 ; i < Size ; i++)
    {
        if( i!=0 && i%16==0)   //if one line of hex printing is complete...
        {
            printf( "         ");
            for(j=i-16 ; j<i ; j++)
            {
                if(data[j]>=32 && data[j]<=128)
                    printf( "%c",(unsigned char)data[j]); //if its a number or alphabet

                else printf( "."); //otherwise print a dot
            }
            printf( "\n");
        }

        if(i%16==0) printf( "   ");
            printf( " %02X",(unsigned int)data[i]);

        if( i==Size-1)  //print the last spaces
        {
            for(j=0;j<15-i%16;j++)
            {
              printf( "   "); //extra spaces
            }

            printf( "         ");

            for(j=i-i%16 ; j<=i ; j++)
            {
                if(data[j]>=32 && data[j]<=128)
                {
                  printf( "%c",(unsigned char)data[j]);
                }
                else
                {
                  printf( ".");
                }
            }

            printf(  "\n" );
        }
    }
}

unsigned short checksum(unsigned short *ptr,int nbytes)
{
    register long sum;
    unsigned short oddbyte;
    register short answer;

    sum=0;
    while(nbytes>1) {
        sum+=*ptr++;
        nbytes-=2;
    }
    if(nbytes==1) {
        oddbyte=0;
        *((u_char*)&oddbyte)=*(u_char*)ptr;
        sum+=oddbyte;
    }

    sum = (sum>>16)+(sum & 0xffff);
    sum = sum + (sum>>16);
    answer=(short)~sum;

    return(answer);
}

