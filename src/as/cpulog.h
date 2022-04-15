/*
 * Copyright (c) 2021 Cisco and/or its affiliates.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at:
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>

/**
 * CPU LOG
*/

/* struct */
typedef struct log_cpu_t log_cpu_t;

struct log_cpu_t
{
        /* info in /proc/stat */
        long long unsigned int user;
        long long unsigned int nice;
        long long unsigned int system;
        long long unsigned int idle;
        /* added between Linux 2.5.41 and 2.6.33, see man proc(5) */
        long long unsigned int iowait;
        long long unsigned int irq;
        long long unsigned int softirq;
        long long unsigned int steal;
        long long unsigned int guest;
        long long unsigned int guestnice;
        /* local cache for calculation */
        long long unsigned int idle_sum;
        long long unsigned int total;
        long long unsigned int prev_idle_sum;
        long long unsigned int prev_total;
        /* output */
        double loadavg;

        // /* functions */
        // long long unsigned int (*cal_total)(log_cpu_t *);
        // long long unsigned int (*cal_idle)(log_cpu_t *);
        // int (*get_stat)(log_cpu_t *);

        struct funcs {
                long long unsigned int (*cal_total)(log_cpu_t *);
                long long unsigned int (*cal_idle)(log_cpu_t *);
                int (*get_stat)(log_cpu_t *);
                double (*cal_load)(log_cpu_t *);
        } f;
};

int log_cpu_t_stat_scan (log_cpu_t * self);

static inline long long unsigned int log_cpu_t_cal_total (log_cpu_t * self);
static inline long long unsigned int log_cpu_t_cal_idle (log_cpu_t * self);
static inline double log_cpu_t_cal_load (log_cpu_t * self);
void cpu_init (log_cpu_t * lc);
double get_update_cpu (log_cpu_t * lc);

extern log_cpu_t cpu_main;
