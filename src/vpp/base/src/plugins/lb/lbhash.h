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

/**
 * vppinfra already includes tons of different hash tables.
 * MagLev flow table is a bit different. It has to be very efficient
 * for both writing and reading operations. But it does not need to
 * be 100% reliable (write can fail). It also needs to recycle
 * old entries in a lazy way.
 *
 * This hash table is the most dummy hash table you can do.
 * Fixed total size, fixed bucket size.
 * Advantage is that it could be very efficient (maybe).
 *
 */

#ifndef LB_PLUGIN_LB_LBHASH_H_
#define LB_PLUGIN_LB_LBHASH_H_

#include <vnet/vnet.h>
#include <vppinfra/lb_hash_hash.h>
#include <lb/stats.h>

#if defined (__SSE4_2__)
#include <immintrin.h>
#endif

/*
 * @brief Number of entries per bucket.
 */
#define LBHASH_ENTRY_PER_BUCKET 4

#define LB_HASH_DO_NOT_USE_SSE_BUCKETS 0

/*
 * @brief One bucket contains 4 entries.
 * Each bucket takes one 64B cache line in memory.
 */
typedef struct {
  CLIB_CACHE_LINE_ALIGN_MARK (cacheline0);
  u32 hash[LBHASH_ENTRY_PER_BUCKET];
  u32 timeout[LBHASH_ENTRY_PER_BUCKET];
  u32 vip[LBHASH_ENTRY_PER_BUCKET];
  u32 value[LBHASH_ENTRY_PER_BUCKET];
#ifdef LB_STATS
  f32 t_last[LBHASH_ENTRY_PER_BUCKET]; /* last timestamp */
  f32 t_init[LBHASH_ENTRY_PER_BUCKET]; /* initial timestamp */
  u32 ack_last[LBHASH_ENTRY_PER_BUCKET]; /* last ack number */
  u32 ack_init[LBHASH_ENTRY_PER_BUCKET]; /* initial ack number */
  u32 tsecr_last[LBHASH_ENTRY_PER_BUCKET]; /* latest tsecr from server */
  u32 src_ip[LBHASH_ENTRY_PER_BUCKET]; /* src ip entropy for consistency checking */
  u16 src_port[LBHASH_ENTRY_PER_BUCKET]; /* src port entropy for consistency checking */
  u16 win_last[LBHASH_ENTRY_PER_BUCKET]; /* last TCP window size */
  u8 tcp_flag[LBHASH_ENTRY_PER_BUCKET]; /* tcp flags */
#endif // LB_STATS
} lb_hash_bucket_t;

typedef struct {
  u32 buckets_mask;
  u32 timeout;
  lb_hash_bucket_t buckets[];
} lb_hash_t;

#define lb_hash_nbuckets(h) (((h)->buckets_mask) + 1)
#define lb_hash_size(h) ((h)->buckets_mask + LBHASH_ENTRY_PER_BUCKET)

#define lb_hash_foreach_bucket(h, bucket) \
  for (bucket = (h)->buckets; \
	bucket < (h)->buckets + lb_hash_nbuckets(h); \
	bucket++)

#define lb_hash_foreach_entry(h, bucket, i) \
    lb_hash_foreach_bucket(h, bucket) \
      for (i = 0; i < LBHASH_ENTRY_PER_BUCKET; i++)

#define lb_hash_foreach_valid_entry(h, bucket, i, now) \
    lb_hash_foreach_entry(h, bucket, i) \
       if (!clib_u32_loop_gt((now), bucket->timeout[i]))

#ifdef LB_STATS
/* For established flows | state in {SYNed, ACKed, PSHACKed} */
static_always_inline void
bucket_stat_update_get(lb_hash_bucket_t *bucket, u32 index, u32 time_now_sec, stat_buffer_t *buffer, lb_vip_shm_t *vip_shm, const u32 found_value)
{
  ref_lb_t *ref_lb = vip_shm->ref_lb;
  ref_as_t *ref_as = shm_get_as_ref(vip_shm, found_value);
  as_stat_t *stat = shm_get_as_stat(vip_shm, found_value);
  // reservoir_lb_t *reservoir_lb = vip_shm->res_lb;
  reservoir_as_t *reservoir_as = shm_get_as_reservoir(vip_shm, found_value);
  if_inconsistent (bucket, index, buffer)
  {
    stat->n_cls++;
    return;
  }

  /* Get tcp flags */
  u8 tcp_flag = buffer->tcp_flag;
  u8 tcp_flag_prev = bucket->tcp_flag[index];
  /* Initialize packet type */
  u8 packet_type = SPT_NORM;
  /* Initialize reservoir sampling id */
  u8 res_id = rand() % RESERVOIR_N_BIN;
  /* update iat_p for res_as */
  f32 iat_p = buffer->time_now - ref_as->t_last_packet;
  ref_as->t_last_packet = buffer->time_now;
  tv_pair_f_t tv_buffer_f = {buffer->time_now, iat_p};
  register_reservoir_as(reservoir_as, iat_p, res_id, tv_buffer_f);
  
  if_flag_has_ack (tcp_flag)        // current_flag & ACK == TRUE
  {
    u32 ack_current = buffer->tcp_ack;
    if_flag_not_only_ack (tcp_flag)
    {
      if_flag_has_rst (tcp_flag)           // a) current_flag == RSTACK
      {
        bucket->timeout[index] = time_now_sec - 1; // evict the bucket for this flow by updating its timeout
        packet_type = SPT_FIRST_FIN;
        f32 fct = buffer->time_now - bucket->t_init[index];  // get flow complete time
        f32 iat_ppf = buffer->time_now - bucket->t_last[index];
        buffer->d_n_flow = -1;
        stat->n_fct++;
        // put flow duration into reservoir sampling memory
        tv_buffer_f.v = fct;
        register_reservoir_as(reservoir_as, fct, res_id, tv_buffer_f);
        tv_buffer_f.v = iat_ppf;
        register_reservoir_as(reservoir_as, iat_ppf, res_id, tv_buffer_f);
      }
      else if_flag_has_psh (tcp_flag)       // b) current_flag == PSHACK
      {
        u32 ack_last = bucket->ack_last[index];
        if (PREDICT_TRUE (ack_current == ack_last)) // new query
        {
          packet_type = SPT_PSHACK;
          bucket->ack_init[index] = ack_current; // update ack_init here to cope with multi-query flow
        }
        else if (PREDICT_TRUE (ack_current < ack_last))
        {
          update_stat_cnt (rtr, PSHACK);
        }
        else // for state == SYNed -> always ack1 > ack0 -> out of order
        {
          update_stat_cnt (ooo, PSHACK);
        }
      }
      else                                // f) current_flag beyond scope
      {
        packet_type = SPT_BEYOND_SCOPE;
      }
    }
    else                                  // c) current_flag == ACK
    {
      if_flag_has_ack (tcp_flag_prev)     // 2) / 3) state == ACKed / PSHACKed
      {
        u32 ack_last = bucket->ack_last[index];
        if (PREDICT_TRUE (ack_current > ack_last)) // normal ack
        {
          /* get n_byte to buffer */
          u32 byte_p = ack_current - bucket->ack_last[index];
          u32 win = (u32) buffer->tcp_win;
          int32_t dwin = win - (int32_t) bucket->win_last[index];
          bucket->win_last[index] = buffer->tcp_win;
          stat->n_norm_ack++;

          tv_pair_t tv_buffer = {buffer->time_now, dwin};
          tv_pair_u_t tv_buffer_u = {buffer->time_now, ack_current - bucket->ack_init[index]}; // current flow's accumulated byte
          tv_buffer_f.v = buffer->time_now - bucket->t_init[index]; // flow duration
          register_reservoir_as(reservoir_as, d_win, res_id, tv_buffer);
          register_reservoir_as(reservoir_as, byte_f, res_id, tv_buffer_u);
          register_reservoir_as(reservoir_as, flow_duration, res_id, tv_buffer_f);
          tv_buffer_u.v = byte_p;
          register_reservoir_as(reservoir_as, byte_p, res_id, tv_buffer_u);
          tv_buffer_u.v = win;
          register_reservoir_as(reservoir_as, win, res_id, tv_buffer_u);
          
          /* update dpt and its baseline */
          u32 tsecr = buffer->tsecr;
          if_tsecr_valid (tsecr) // get processing time on server side w/ tsecr
          {
            if (PREDICT_FALSE(bucket->ack_last[index] == bucket->ack_init[index])) // first data packet
            {
              get_process_time(_1st, res_id);
              packet_type = SPT_FIRST_DATA;
            }
            else if (PREDICT_FALSE(buffer->tsecr > bucket->tsecr_last[index])) /* only cares about packets with higher tsecr */
            {
              get_process_time(_gen, res_id);
            }
          }
#ifdef LB_DEBUG
          else // no tcp timestamp configured
            packet_type = SPT_TS_INVALID;
#endif
          /* update last acks */
          bucket->ack_last[index] = ack_current;
        }
        else if (PREDICT_TRUE (ack_current == ack_last))
        {
          stat->n_dpk++;
          packet_type = SPT_DUP_ACK;
        }
        else
        {
          update_stat_cnt (ooo, ACK);
        }
      }
      else  // 1) state == SYNed (first ack)
      {
        /* initialize ack number */
        bucket->ack_last[index] = ack_current;
        /* initialize TCP window size */
        bucket->win_last[index] = buffer->tcp_win;
        /* update packet type */
        packet_type = SPT_FIRST_ACK;
        /* initialize tsecr if valid */
        u32 tsecr = buffer->tsecr;
        if_tsecr_valid (tsecr) {
          bucket->tsecr_last[index] = tsecr;
          if (PREDICT_FALSE(ref_as->t0_ecr == 0)) {
            if (PREDICT_FALSE(ref_lb->t0) == 0) ref_lb->t0 = (u32) (bucket->t_last[index] * 1000) + PT_OFFSET; // initialize first timestamp on LB node to help calculate pt_1st and pt_gen for each AS
            ref_as->t0_ecr = ref_lb->t0 - tsecr; // assume the first process can be slow (exploit t0_ecr as delta_base)
          }
        }
        /* update lat_synack */
        f32 lat_synack = buffer->time_now - bucket->t_init[index];
        tv_buffer_f.v = lat_synack;
        register_reservoir_as(reservoir_as, lat_synack, res_id, tv_buffer_f);
      }
      /* update iat_ppf */
      f32 iat_ppf = buffer->time_now - bucket->t_last[index];
      tv_buffer_f.v = iat_ppf;
      register_reservoir_as(reservoir_as, iat_ppf, res_id, tv_buffer_f);
    }
  }
  else if_flag_is_syn (tcp_flag)          // d) current_flag == SYN
  {
    update_stat_cnt (rtr, SYN);
  }
  else if_flag_is_rst (tcp_flag)          // e) current_flag == RST
  {
    update_stat_cnt (rtr, RST);
  }
  else                                    // f) current_flag beyond scope
  {
    packet_type = SPT_BEYOND_SCOPE;
  }

  /* for every packet */
  if (PREDICT_TRUE(packet_type < SPT_rtr_SYN))
  {
    /* if not weird, update state */
    bucket->tcp_flag[index] = tcp_flag;
  }
  bucket->t_last[index] = buffer->time_now;
  stat->n_packet++;
  stat->n_flow_on *= N_FLOW_ON_DECAY; 
  stat->n_flow_on += buffer->d_n_flow;
  
}

/* For newly entered flows | state == IDLE */
static_always_inline void
bucket_stat_update_put(lb_hash_bucket_t *bucket, u32 index, u32 time_now_sec, stat_buffer_t *buffer, lb_vip_shm_t *vip_shm, const u32 found_value)
{
  ref_lb_t *ref_lb = vip_shm->ref_lb;
  ref_as_t *ref_as = shm_get_as_ref(vip_shm, found_value);
  as_stat_t *stat = shm_get_as_stat(vip_shm, found_value);
  reservoir_lb_t *reservoir_lb = vip_shm->res_lb;
  reservoir_as_t *reservoir_as = shm_get_as_reservoir(vip_shm, found_value);
  u8 res_id = rand() % RESERVOIR_N_BIN;
  tv_pair_f_t tv_buffer_f = {buffer->time_now, 0.};


  if (bucket->tcp_flag[index] != TCP_FLAGS_NULL && bucket->tcp_flag[index] != TCP_FLAGS_RSTACK) // last flow timeout-ed without complete
  {
    if ((bucket->src_ip[index] == buffer->src_ip) && (bucket->src_port[index] == buffer->src_port)) // same timeout-ed flow
    {
      if (bucket->value[index] != found_value) // same source but switched AS, wrap up last flow
      {
        u32 value_last = bucket->value[index];
        as_stat_t *stat_last = shm_get_as_stat(vip_shm, value_last);
        reservoir_as_t *reservoir_as_last = shm_get_as_reservoir(vip_shm, value_last);
        f32 fct = buffer->time_now - bucket->t_init[index] - LB_DEFAULT_FLOW_TIMEOUT;  /* guess flow complete time */
        tv_buffer_f.v = fct;
        register_reservoir_as(reservoir_as_last, fct, res_id, tv_buffer_f);
        stat_last->n_flow_on--;
        stat_last->n_fct++;
      }
      else // same source and same AS, no process is required
      {
        return;
      }
    }
    else // a new flow coming, wrap up last flow
    {
      u32 value_last = bucket->value[index];
      as_stat_t *stat_last = shm_get_as_stat(vip_shm, value_last);
      reservoir_as_t *reservoir_as_last = shm_get_as_reservoir(vip_shm, value_last);
      f32 fct = buffer->time_now - bucket->t_init[index] - LB_DEFAULT_FLOW_TIMEOUT;  /* guess flow complete time */
      tv_buffer_f.v = fct;
      register_reservoir_as(reservoir_as_last, fct, res_id, tv_buffer_f);
      stat_last->n_flow_on--;
      stat_last->n_fct++;
    }
  }
  
  /* Get tcp flags */
  u8 tcp_flag = buffer->tcp_flag;
  // u8 tcp_flag_prev = bucket->tcp_flag[index];
  /* Initialize packet type */
  u8 packet_type = SPT_NORM;

  if_flag_is_syn (tcp_flag)          // d) current_flag == SYN
  {
    if (PREDICT_TRUE(ref_as->t_last_flow > 0.1)) {
      f32 iat_f = buffer->time_now - ref_as->t_last_flow; // update iat_f for AS
      tv_buffer_f.v = iat_f;
      register_reservoir_as(reservoir_as, iat_f, res_id, tv_buffer_f);
      iat_f = buffer->time_now - ref_lb->t_last_flow; // update iat_f for VIP
      tv_buffer_f.v = iat_f;
      reservoir_lb->iat_f_lb[res_id] = tv_buffer_f;
    }
    else // first SYN packet for the AS
    {
      if (PREDICT_FALSE(ref_lb->t0 <= 1e-6)) { // first SYN packet for the VIP
        ref_lb->t0 = buffer->time_now;
      }
    }
    register_new_flow (FIRST_SYN);
  }
  else if_flag_is_rst (tcp_flag)          // e) current_flag == RST
  {
    update_stat_cnt (rtr, RST);
    bucket->timeout[index] = time_now_sec - 1; // evict the bucket for this flow by updating its timeout
  }
  else                                    // f) current_flag beyond scope
  {
    packet_type = SPT_BEYOND_SCOPE;
  }

  /* for every packet */
  if (PREDICT_TRUE(packet_type < SPT_rtr_SYN))
  {
    /* if not weird, update state */
    bucket->tcp_flag[index] = tcp_flag;
  }
  bucket->t_last[index] = buffer->time_now;
  stat->n_packet++;
  f32 iat_p = buffer->time_now - ref_as->t_last_packet;
  tv_buffer_f.v = iat_p;
  register_reservoir_as(reservoir_as, iat_p, res_id, tv_buffer_f);
  ref_as->t_last_packet = buffer->time_now;
  // stat->n_flow_on *= N_FLOW_ON_DECAY; 
  stat->n_flow_on += buffer->d_n_flow;

}
#endif // LB_STATS

static_always_inline
lb_hash_t *lb_hash_alloc(u32 buckets, u32 timeout)
{
  if (!is_pow2(buckets))
    return NULL;

  // Allocate 1 more bucket for prefetch
  u32 size = ((uword)&((lb_hash_t *)(0))->buckets[0]) +
      sizeof(lb_hash_bucket_t) * (buckets + 1);
  u8 *mem = 0;
  lb_hash_t *h;
  vec_alloc_aligned(mem, size, CLIB_CACHE_LINE_BYTES);
  clib_memset(mem, 0, size);
  h = (lb_hash_t *)mem;
  h->buckets_mask = (buckets - 1);
  h->timeout = timeout;
  return h;
}

static_always_inline
void lb_hash_free(lb_hash_t *h)
{
  u8 *mem = (u8 *)h;
  vec_free(mem);
}

static_always_inline
void lb_hash_prefetch_bucket(lb_hash_t *ht, u32 hash)
{
  lb_hash_bucket_t *bucket = &ht->buckets[hash & ht->buckets_mask];
  CLIB_PREFETCH(bucket, sizeof(*bucket), READ);
}

static_always_inline
#ifdef LB_STATS
void lb_hash_get(lb_hash_t *ht, u32 hash, u32 vip, u32 time_now,
		 u32 *available_index, u32 *found_value, stat_buffer_t *buffer, lb_vip_shm_t *vip_shm)
#else
void lb_hash_get(lb_hash_t *ht, u32 hash, u32 vip, u32 time_now,
		 u32 *available_index, u32 *found_value)
#endif // LB_STATS
{
  lb_hash_bucket_t *bucket = &ht->buckets[hash & ht->buckets_mask];
  *found_value = 0;
  *available_index = ~0;
#if __SSE4_2__ && LB_HASH_DO_NOT_USE_SSE_BUCKETS == 0
  u32 bitmask, found_index;
  __m128i mask;

  // mask[*] = timeout[*] > now
  mask = _mm_cmpgt_epi32(_mm_loadu_si128 ((__m128i *) bucket->timeout),
			 _mm_set1_epi32 (time_now));
  // bitmask[*] = now <= timeout[*/4]
  bitmask = (~_mm_movemask_epi8(mask)) & 0xffff;
  // Get first index with now <= timeout[*], if any.
  *available_index = (bitmask)?__builtin_ctz(bitmask)>>2:*available_index;

#ifdef LB_STATS
  /* if received is not a SYN packet, either go to the same bucket if a state is found, or "pretend" the bucket is full and assign according to hashing table */
  *available_index = (buffer->tcp_flag & TCP_FLAGS_SYN)?*available_index:~0;
#endif /* LB_STATS */

  // mask[*] = (timeout[*] > now) && (hash[*] == hash)
  mask = _mm_and_si128(mask,
		       _mm_cmpeq_epi32(
			   _mm_loadu_si128 ((__m128i *) bucket->hash),
			   _mm_set1_epi32 (hash)));

  // Load the array of vip values
  // mask[*] = (timeout[*] > now) && (hash[*] == hash) && (vip[*] == vip)
  mask = _mm_and_si128(mask,
		       _mm_cmpeq_epi32(
			   _mm_loadu_si128 ((__m128i *) bucket->vip),
			   _mm_set1_epi32 (vip)));

  // mask[*] = (timeout[*x4] > now) && (hash[*x4] == hash) && (vip[*x4] == vip)
  bitmask = _mm_movemask_epi8(mask);
  // Get first index, if any
  found_index = (bitmask)?__builtin_ctzll(bitmask)>>2:0;
  ASSERT(found_index < 4);
  *found_value = (bitmask)?bucket->value[found_index]:*found_value;
  bucket->timeout[found_index] =
      (bitmask)?time_now + ht->timeout:bucket->timeout[found_index];
#ifdef LB_STATS
  /* If found index of bucket */
  if (PREDICT_TRUE (bitmask))
  {
    // bucket_stat_update_get(bucket, found_index, time_now, buffer, shm_get_as_ref(vip_shm, *found_value), shm_get_as_stat(vip_shm, *found_value));
    bucket_stat_update_get(bucket, found_index, time_now, buffer, vip_shm, *found_value);
  }
#endif // LB_STATS
#else
  u32 i;
  for (i = 0; i < LBHASH_ENTRY_PER_BUCKET; i++) {
      u8 cmp = (bucket->hash[i] == hash && bucket->vip[i] == vip);
      u8 timeouted = clib_u32_loop_gt(time_now, bucket->timeout[i]);
      *found_value = (cmp || timeouted)?*found_value:bucket->value[i];
      bucket->timeout[i] = (cmp || timeouted)?time_now + ht->timeout:bucket->timeout[i];
      *available_index = (timeouted && (*available_index == ~0))?i:*available_index;

      if (!cmp)
	return;
  }
#endif
}

static_always_inline
u32 lb_hash_available_value(lb_hash_t *h, u32 hash, u32 available_index)
{
  return h->buckets[hash & h->buckets_mask].value[available_index];
}

static_always_inline
#ifdef LB_STATS
void lb_hash_put(lb_hash_t *h, u32 hash, u32 value, u32 vip,
		 u32 available_index, u32 time_now, stat_buffer_t *buffer, lb_vip_shm_t *vip_shm)
#else
void lb_hash_put(lb_hash_t *h, u32 hash, u32 value, u32 vip,
		 u32 available_index, u32 time_now)
#endif // LB_STATS
{
  lb_hash_bucket_t *bucket = &h->buckets[hash & h->buckets_mask];
#ifdef LB_STATS
  // bucket_stat_update_put (bucket, available_index, time_now, buffer, shm_get_as_ref(vip_shm, value), shm_get_as_stat(vip_shm, value));
  bucket_stat_update_put (bucket, available_index, time_now, buffer, vip_shm, value);
#endif // LB_STATS
  bucket->hash[available_index] = hash;
  bucket->value[available_index] = value;
  bucket->timeout[available_index] = time_now + h->timeout;
  bucket->vip[available_index] = vip;
}

static_always_inline
u32 lb_hash_elts(lb_hash_t *h, u32 time_now)
{
  u32 tot = 0;
  lb_hash_bucket_t *bucket;
  u32 i;
  lb_hash_foreach_valid_entry(h, bucket, i, time_now) {
    tot++;
  }
  return tot;
}

#endif /* LB_PLUGIN_LB_LBHASH_H_ */
