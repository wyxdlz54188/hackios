/*
 * TrustCache/API.h -- the interface XNU 17.0 expects from Apple's libTrustCache.
 *
 * Apple ships this header in no SDK (13.3 and 14.5 were both checked) and libTrustCache itself is
 * closed, but XNU 17.0's own sources include <TrustCache/API.h> from osfmk/vm/pmap_cs.h,
 * bsd/sys/trust_caches.h and libkern/libkern/amfi/amfi.h, and this port's libkern/amfi/miniamfi.c
 * implements the interface. This header is the port's reconstruction: the types and constants the
 * tree uses, nothing more. amfi.h declares TrustCacheInterface_t itself (its own typedefs of the
 * function pointers), so that struct is not repeated here.
 *
 * Nothing loads a trust cache on this port (miniamfi answers "not found" to every query), so what
 * matters is that every user agrees -- the layout is not Apple's, it is ours.
 *
 * Install: xnu-src/xnu-10002.1.13/EXTERNAL_HEADERS/TrustCache/API.h (a directory on the kernel's
 * include path).
 */
#ifndef _TRUSTCACHE_API_H_
#define _TRUSTCACHE_API_H_

#include <stdint.h>
#include <stddef.h>
#include <stdbool.h>

#define kTCEntryHashSize        20
#define kUUIDSize               16

/* Which kind of trust cache a module or a query is about. */
typedef enum {
	kTCTypeInvalid = 0,
	kTCTypeStatic,
	kTCTypeLegacy,
	kTCTypeEngineering,
	kTCTypeLTRS,
	kTCTypeDTRS,
	kTCTypeCryptex1BootOS,
	kTCTypeCryptex1BootApp,
	kTCTypeConfig,
	kTCTypeTotal,
} TCType_t;

/* What a query looks at. */
typedef enum {
	kTCQueryTypeAll = 0,
	kTCQueryTypeStatic,
	kTCQueryTypeLoadable,
	kTCQueryTypeTotal,
} TCQueryType_t;

/* What a module can do; a bit set per capability. */
typedef uint64_t TCCapabilities_t;
enum {
	kTCCapabilityNone = 0,
};

/* The components a call can fail in: the "component" of a TCReturn. */
enum {
	kTCComponentLoadModule = 0,
	kTCComponentLoad,
	kTCComponentQuery,
	kTCComponentModuleCapabilities,
	kTCComponentQueryTCType,
	kTCComponentQueryCapabilities,
	kTCComponentQueryHashType,
	kTCComponentQueryFlags,
	kTCComponentQueryConstraintCategory,
	kTCComponentConstructInvalid,
	kTCComponentCheckRuntimeForUUID,
	kTCComponentExtractModule,
	kTCComponentGetModule,
	kTCComponentGetUUID,
};

/* How a call failed: the "error" of a TCReturn. */
enum {
	kTCReturnSuccess = 0,
	kTCReturnNotFound,
	kTCReturnUnsupported,
	kTCReturnInvalidArguments,
	kTCReturnDuplicate,
	kTCReturnError,
};

typedef struct {
	uint8_t     component;
	uint8_t     error;
	uint16_t    uniqueError;
} TCReturn_t;

static inline TCReturn_t
buildTCRet(uint8_t component, uint8_t error, uint16_t uniqueError)
{
	TCReturn_t ret = { component, error, uniqueError };
	return ret;
}

/*
 * A loaded module, the runtime that holds them, and the mutable part of that runtime. Opaque to every
 * user in this tree: the port never loads one, and the code that would (kern_trustcache.c) only hands
 * the pointers back to the interface amfi.h declares.
 */
typedef struct {
	uint64_t    opaque[8];
} TrustCache_t;

typedef struct {
	uint64_t    opaque[16];
	/* kern_trustcache.c reads this one field of the runtime (line 857 of Apple's file). */
	bool        allowEngineeringTC;
} TrustCacheRuntime_t;

typedef struct {
	uint64_t    opaque[16];
} TrustCacheMutableRuntime_t;

/* What a successful query leaves behind for the caller to read. */
typedef struct {
	uint8_t     hashType;
	uint8_t     type;
	uint8_t     constraintCategory;
	uint8_t     reserved;
	uint64_t    flags;
	TCCapabilities_t capabilities;
	uint8_t     hash[kTCEntryHashSize];
} TrustCacheQueryToken_t;

/*
 * The per-type table kern_trustcache.c indexes when it decides whether the caller may load this kind of
 * trust cache. The port loads none, so every entry says "no entitlement needed" (NULL); the shape is
 * what the caller reads.
 */
struct tc_type_config {
	const char *entitlementValue;
};
static const struct tc_type_config TCTypeConfig[kTCTypeTotal] = { { NULL } };

/*
 * What libTrustCache would do when AMFI starts: take the two halves of the runtime and the policy
 * switches. The port has no trust caches, so the runtime stays empty and every query says "not found"
 * (miniamfi.c). The switches are accepted and ignored.
 */
struct _img4_runtime;

static inline void
trustCacheInitializeRuntime(TrustCacheRuntime_t *runtime, TrustCacheMutableRuntime_t *mutable_runtime,
    bool allow_second_static_cache, bool allow_engineering_caches, bool allow_legacy_caches,
    const struct _img4_runtime *img4_runtime)
{
	(void)runtime; (void)mutable_runtime;
	(void)allow_second_static_cache; (void)allow_engineering_caches; (void)allow_legacy_caches;
	(void)img4_runtime;
}

#endif /* _TRUSTCACHE_API_H_ */
