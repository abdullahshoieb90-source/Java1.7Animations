### v2.7.0

- Replaced the v2.5.3 spear-compatibility approximation with a source-derived port of Minecraft Java 1.21.11's `SpearAnimations` in both first and third person
- Ported per-tier `UseParams` timing, normalized STAB phases (`0.05`, `0.20`, `0.40`), Java easing (`outBack`, `inOutExpo`, `inOutElastic`, and the other source curves), arm poses, pivot-based item transforms, forward movement, and kinetic-hit feedback
- Added Java spear display geometry and first-/third-person attachable transforms for wooden, stone, copper, iron, golden, diamond, and netherite spears while preserving each tier's hit sound
- Third-person attack and use transforms now compose in Java's `ItemInHandLayer` order; custom armor arms follow the same hold/use/attack poses
- Enabled the complete pipeline in all 12 subpacks and removed the obsolete Bedrock attachable-variable approximation
- Added an independent Java reference implementation and numeric Molang regression tests, including first-person `PoseStack` positions, attack/use timing, hit feedback, and neutral endpoints; the full suite now contains 35 tests
- Cross-checked Bedrock `rightitem` conversion against the [Fixed Vanilla integration in MADLAD3718/The-Crew-SMP](https://github.com/MADLAD3718/The-Crew-SMP)
- Static/source-derived verification only: visual equivalence still needs to be checked on a Minecraft Bedrock device

### v2.5.3

- Fixed melee spears being invisible in first person on Minecraft Bedrock 1.21.130 and newer
- Added spear hold, use, and attack animations, including the attachable variables required by the newer rendering pipeline
- Enabled the spear animations in all 12 subpack configurations, including the console eat-animation variants
- Prevented the generic arm-swing animation from conflicting with spear attacks
- First-person compatibility adapted from [BrineFlashYT's upstream fix](https://github.com/ambiennt/Java1.7Animations/pull/18) and covered by regression tests

### v2.5.1

- Added `No Armor Overlay + Console Edition Eat Animation` subpack
- The trident charge animation now properly plays when the player is crawling
- The crawl animation no longer transforms the player root based on head pitch
- Minor bug fixes

### v2.5.0

- Fixed most major bugs introduced since Minecraft Bedrock Edition v1.19.0, *within the capacity that resource packs allow*
    - **Minecraft Bedrock v1.21.0 to v1.21.51 are officially supported**, but future versions can't be guaranteed
- **Proper cape/persona support!** (thanks to [Rainvay_ZCYF](https://mcpedl.com/user/zouchenyunfei/) for sharing a workaround!)
    - The cape overlay pack is now deprecated for this reason
- Revamped subpack configurations
- Proper leather armor color support while armor hurt overlay is active (for applicable subpacks)
    - This means that leather armor textures are no longer overwritten
- Tweaked armor hurt overlay color values
    - `Redder Armor Overlay` subpacks now use the same RGBA values as vanilla Minecraft Bedrock Edition (`r=1.0, g=0.0, b=0.0, a=0.6`)
- Improved shield animations
    - Now uses the shield blocking flag instead of the player sneaking flag to determine whether a player should block with their shield
- Improved elytra animations and model scale
- Tweaked spyglass animations/1st person positioning
- Tweaked trident wielding animations
- Tweaked swimming animations
- Tweaked crawling animations
- Projectile particles start to emit after 1 tick (instead of 2) after spawning
- Damage particle color now more closely aligns with Minecraft Java Edition
- Damage particles now emit at the center of a player's hitbox
- Armor and elytra models now use `textures/misc/enchanted_actor_glint` instead of `textures/misc/enchanted_item_glint` for the enchantment glint texture
- The player's arms no longer bob while being rendered in menus, and instead are fixed to match the angle of that in Minecraft Bedrock Edition v1.12.1 and lower
- Improved the eat animation to match Minecraft Console Edition (for applicable subpacks)
- Partially fixed armor trims not showing
    - Currently it isn't possible to show armor trims on the hurt armor overlay due to resource pack limitations
- Banners now properly render on shields
- The vanilla fire overlay now correctly shows on mobs