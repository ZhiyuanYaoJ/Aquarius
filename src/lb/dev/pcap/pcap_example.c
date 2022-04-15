/*
 * pcap_example.c
 *
 *  Created on: Apr 28, 2016
 *      Author: jiaziyi
 */


#include<pcap.h>
#include<stdio.h>
#include<stdlib.h>
#include<string.h>

#include "header.h"

#include<sys/socket.h>
#include<arpa/inet.h>

#include "pcap_example.h"
#include "header.h"


#include <stdint.h>  // <cstdint> is preferred in C++, but stdint.h works.

#ifdef _MSC_VER
# include <intrin.h>
#else
# include <x86intrin.h>
#endif

// optional wrapper if you don't want to just use __rdtsc() everywhere
uint64_t readTSC() {
    // _mm_lfence();  // optionally wait for earlier insns to retire before reading the clock
    uint64_t tsc = __rdtsc();
    // _mm_lfence();  // optionally block later instructions until rdtsc retires
    return tsc;
}

// requires a Nehalem or newer CPU.  Not Core2 or earlier.  IDK when AMD added it.
uint64_t readTSCp() {
    unsigned dummy;
    return __rdtscp(&dummy);  // waits for earlier insns to retire, but allows later to start
}

//some global counter
int tcp=0,udp=0,icmp=0,others=0,igmp=0,total=0,i,j;


int main(int argc, char *argv[])
{	
	pcap_if_t *all_dev, *dev;
	 pcap_t *handle;		/* Session handle */
	 		/* Device to sniff on */
	 char errbuf[PCAP_ERRBUF_SIZE],dev_list[30][2];	/* Error string */
	 struct bpf_program fp;		/* The compiled filter expression */
	 char filter_exp[] = "";	/* The filter expression */
	 bpf_u_int32 mask;		/* The netmask of our sniffing device */
	 bpf_u_int32 net;		/* The IP of our sniffing device */
	//get all available devices

	if(pcap_findalldevs(&all_dev, errbuf))
	{
		fprintf(stderr, "Unable to find devices: %s", errbuf);
		exit(1);
	}

	if(all_dev == NULL)
	{
		fprintf(stderr, "No device found. Please check that you are running with root \n");
		exit(1);
	}

	printf("Available devices list: \n");
	int c = 1;

	for(dev = all_dev; dev != NULL; dev = dev->next)
	{
		printf("#%d %s : %s \n", c, dev->name, dev->description);
		if(dev->name != NULL)
		{
			strncpy(dev_list[c], dev->name, strlen(dev->name));
		}
		c++;
	}



	printf("Please choose the monitoring device (e.g., en0):\n");
	char *dev_name = malloc(20);
	fgets(dev_name, 20, stdin);
	*(dev_name + strlen(dev_name) - 1) = '\0'; //the pcap_open_live don't take the last \n in the end

	//look up the chosen device
	int ret = pcap_lookupnet(dev_name, &net, &mask, errbuf);
	if(ret < 0)
	{
		fprintf(stderr, "Error looking up net: %s \n", dev_name);
		exit(1);
	}

	struct sockaddr_in addr;
	addr.sin_addr.s_addr = net;
	char ip_char[100];
	inet_ntop(AF_INET, &(addr.sin_addr), ip_char, 100);
	printf("NET address: %s\n", ip_char);

	addr.sin_addr.s_addr = mask;
	memset(ip_char, 0, 100);
	inet_ntop(AF_INET, &(addr.sin_addr), ip_char, 100);
	printf("Mask: %s\n", ip_char);
	handle = pcap_open_live(dev_name, BUFSIZ, 1, 1000, errbuf);
	 if (handle == NULL) {
		 fprintf(stderr, "Couldn't open device %s: %s\n", dev_name, errbuf);
		 return(2);
	 }
	 if (pcap_compile(handle, &fp, filter_exp, 0, net) == -1) {
		 fprintf(stderr, "Couldn't parse filter %s: %s\n", filter_exp, pcap_geterr(handle));
		 return(2);
	 }
	 if (pcap_setfilter(handle, &fp) == -1) {
		 fprintf(stderr, "Couldn't install filter %s: %s\n", filter_exp, pcap_geterr(handle));
		 return(2);
	 }


	//open the device
	//
	//	   pcap_t *pcap_open_live(char *device,int snaplen, int prmisc,int to_ms,
	//	   char *ebuf)
	//
	//	   snaplen - maximum size of packets to capture in bytes
	//	   promisc - set card in promiscuous mode?
	//	   to_ms   - time to wait for packets in miliseconds before read
	//	   times out
	//	   errbuf  - if something happens, place error string here
	//
	//	   Note if you change "prmisc" param to anything other than zero, you will
	//	   get all packets your device sees, whether they are intendeed for you or
	//	   not!! Be sure you know the rules of the network you are running on
	//	   before you set your card in promiscuous mode!!

	//Put the device in sniff loop
	pcap_loop(handle , -1 , process_packet , NULL);

	pcap_close(handle);

	return 0;

}

void process_packet(u_char *args, const struct pcap_pkthdr *header, const u_char *buffer)
{	
	FILE *log_file;
	log_file = fopen("pcap.log", "a");

	if (log_file == NULL) {
		printf("Error!");
		exit(1);
	}

	uint64_t start = readTSC();

//	printf("a packet is received! %d \n", total++);
	// int size = header->len;
	// //printf("%d\n",size);
	// //Get the IP Header part of this packet , excluding the ethernet header
	// struct iphdr *iph = (struct iphdr*)(buffer + sizeof(struct ethhdr));
	// ++total;
	// if(iph->protocol==17) //Check the Protocol and do accordingly...
	// {
	// 	// print_udp_packet(buffer, size);
	// 	// fflush(stdout);
	// }

	int size = header->len;

	//Get the IP Header part of this packet , excluding the ethernet header
	struct iphdr *iph = (struct iphdr*)(buffer + sizeof(struct ethhdr));
	++total;
	
	switch (iph->protocol) //Check the Protocol and do accordingly...
	{
	case 6:  //TCP Protocol
		++tcp;
		print_tcp_packet(buffer, size, log_file);
		fprintf(log_file, "cycles: %ld\n", readTSC() - start);
		fflush(log_file);

		break;

	case 1:  //ICMP Protocol
		++icmp;
		// print_icmp_packet( buffer , size);
		break;

	case 2:  //IGMP Protocol
		++igmp;
		break;


	case 17: //UDP Protocol
		++udp;
		// print_udp_packet(buffer , size);
		break;

	default: //Some Other Protocol like ARP etc.
		++others;
		break;
	}
	// printf("%d %d %d\n", tcp , udp , icmp);
	fclose(log_file	);
	

}

