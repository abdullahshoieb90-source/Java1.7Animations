### v2.6.2

- Fixed the Armor HUD icons still not appearing on Android after v2.6.1:
    - The icon quads are authored at `y=500`, but the player entity scale (`0.9375`) pulled them down to `y=468.75`, outside the `live_player_renderer` viewport. A new root-bone animation (`animation.player.j17_armor_hud`) cancels that scale on the HUD root bone only.
    - The same animation keeps the icons level while swimming/crawling and compensates riding/gliding rotation.
    - The animation is wired into all 12 subpacks and runs only while the player is drawn in the HUD (`q.is_in_ui`).
    - HUD icon controllers now use a fixed `light_color_multiplier` so the icons stay bright.
- Added regression tests for the placement animation and its wiring across all subpacks.

### v2.6.1

- Fixed the Armor HUD icons not rendering on some Bedrock builds (reported on Android):
    - Player scripts now keep updating while the player is drawn off-screen in the HUD (`should_update_effects_offscreen`)
    - The HUD render gate no longer depends on `q.is_on_screen`, which can be false inside `live_player_renderer`
    - HUD quads are no longer hidden by `part_visibility` querying `q.is_on_screen`
    - The HUD material now enables `USE_OVERLAY`, and the icon controllers enable `filter_lighting`
    - Texture/array references in the HUD render controllers were normalized to lowercase
    - The HUD panel is inserted at the front of the HUD root and drawn on a higher layer

### v2.6.0

- Added an always-on **Armor HUD** inspired by XeroxClient's (original implementation — no XeroxClient files are copied): the vanilla armor-points bar is replaced by four equipped-armor item icons above the hotbar
    - Empty-slot placeholders, leather dye tint, and turtle shell / elytra / copper / carved pumpkin support
    - Drawn entirely client-side through a `live_player_renderer`; no behavior pack required
    - HUD position is tweakable via `offset` in `ui/armor_hud.json` (default `[42, -40]`)
    - Enchantment glint on the HUD icons is not simulated; copper icons require a game version that includes copper armor
- The pack validator now accepts materials defined in `materials/*.material` instead of warning about them

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