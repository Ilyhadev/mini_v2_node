/**
 * This program is free software under the GNU General Public License v3.
 * See <https://www.gnu.org/licenses/> for details.
 */

#include <array>
#include <cstddef>
#include <cstdint>
#include "mcu_family_id.hpp"

#ifndef APP_VERSION_MAJOR
#define APP_VERSION_MAJOR 0U
#endif

#ifndef APP_VERSION_MINOR
#define APP_VERSION_MINOR 0U
#endif

#ifndef RELEASE_BUILD
#define RELEASE_BUILD 0U
#endif

#ifndef DIRTY_BUILD
#define DIRTY_BUILD 0U
#endif

#ifndef BUILD_TIMESTAMP_UTC
#define BUILD_TIMESTAMP_UTC 0U
#endif

#ifndef GIT_HASH
#define GIT_HASH 0U
#endif

#ifndef MCU_FAMILY_ID
#define MCU_FAMILY_ID static_cast<std::uint8_t>(McuFamilyId::UNKNOWN)
#endif

namespace {

struct __attribute__((packed)) alignas(16) AppDescriptor {
    std::uint64_t magic = 0x5E4415146FC0C4C7ULL;

    std::array<std::uint8_t, 8> signature{{'A', 'P', 'D', 'e', 's', 'c', '0', '0'}};

    std::uint64_t image_crc = 0U;
    std::uint32_t image_size = 0U;

    std::uint32_t vcs_commit = 0U;

    std::uint8_t version_major = static_cast<std::uint8_t>(APP_VERSION_MAJOR);
    std::uint8_t version_minor = static_cast<std::uint8_t>(APP_VERSION_MINOR);

    std::uint8_t flags = static_cast<std::uint8_t>((RELEASE_BUILD ? 1U : 0U) |
                                                   (DIRTY_BUILD ? 2U : 0U));
    std::uint8_t mcu_family_id = static_cast<std::uint8_t>(MCU_FAMILY_ID);
    std::uint32_t build_timestamp_utc = static_cast<std::uint32_t>(BUILD_TIMESTAMP_UTC);

    std::uint64_t vcs_revision_id = static_cast<std::uint64_t>(GIT_HASH);
    std::array<std::uint8_t, 16> padding{};
};

static const volatile AppDescriptor app_descriptor
    __attribute__((used, section(".app_descriptor")));

static_assert(sizeof(AppDescriptor) == 64U, "Kocherga AppDescriptor must be exactly 64 bytes");

}  // namespace

uint64_t get_firmware_image_crc() {
    return app_descriptor.image_crc;
}
