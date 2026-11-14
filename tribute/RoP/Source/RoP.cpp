/******************************************************************************/
/* Rings of Power — Tribute remake, classic isometric mode (M7, 2D).
 *
 * #023 engine setup: the classic-isometric skeleton.
 * Smooth flat plane + dot walking. No game rules yet (those are later
 * issues: #024 assets, #025 world, #026 logic, #027 combat, #029 dialogue).
 *
 * A flat isometric plane (16x16 diamond tiles) and a dot (the player)
 * that walks smoothly, per-frame, with the arrow keys. The picture updates
 * every frame (60 Hz); the logic tick is separate (later issues).
 *
 * Verified against the ROM where the skeleton touches it:
 *  - the isometric diamond (2:1, TW=2*TH) matches the original's
 *    screen layout (14 px horizontal, 8 px vertical per cell step);
 *  - the plane is a flat render of the room, as in the flat-zoomed ROM.
 * Everything else here is tribute (our invention), labelled as such.
 */
/******************************************************************************/

#include "stdafx.h"

/******************************************************************************/
// Isometric plane: 16x16 diamond tiles, 2:1 (width = 2 * height), as in the
// original's screen layout (a cell step is +14 px x, +8 px y on screen).
static const Int   GRID = 16;
static const Flt   TILE_W = 0.12f; // diamond width  (screen units)
static const Flt   TILE_H = 0.06f; // diamond height (screen units)
static const Flt   SPEED  = 4.0f;  // player speed, cells per second

// Player position in cell coordinates (float = smooth, sub-cell).
static Flt player_x = 8.0f;
static Flt player_y = 8.0f;

// World (cell) -> screen. sx=(cx-cy)*TW/2, sy=(cx+cy)*TH/2, centred so the
// 16x16 grid sits in the middle of the screen (sy offset -GRID*TH/2).
static Vec2 worldToScreen(Flt cx, Flt cy)
{
   Flt sx = (cx - cy) * TILE_W * 0.5f;
   Flt sy = (cx + cy) * TILE_H * 0.5f - GRID * TILE_H * 0.5f;
   return Vec2(sx, sy);
}

/******************************************************************************/
void InitPre()
{
   App.name("Rings of Power - Tribute (Classic)");
   App.flag=APP_MINIMIZABLE|APP_MAXIMIZABLE|APP_RESIZABLE|APP_FULL_TOGGLE|APP_WORK_IN_BACKGROUND;

#ifdef DEBUG
   App.flag|=APP_MEM_LEAKS|APP_BREAKPOINT_ON_ERROR;
#endif

   // Explicit windowed mode (1024x768): the engine's default fills the
   // screen, and DrawState() skips drawing when fullscreen + unfocused
   // (which is always true under Xvfb with no window manager).
   D.mode(1024, 768, false);

   // Data is a symlink (RoP/Data -> ../EsenthelEngine/Data) to the engine's
   // Data folder (shaders, fonts, Gui). DataPath is relative to the current
   // working directory, so run the app from its own dir: cd RoP && ./RoP
   DataPath("Data");
}

/******************************************************************************/
Bool Init()
{
   player_x=8.0f;
   player_y=8.0f;
   return true;
}

/******************************************************************************/
void Shut()
{
}

/******************************************************************************/
Bool Update()
{
   if(Kb.bp(KB_ESC))return false;
   if(!App.active())Time.wait(1);

   // Arrow keys -> world direction. Up=(cx-1,cy-1) is straight up on screen,
   // Down=(cx+1,cy+1) straight down, Left=(cx-1,cy+1) left, Right=(cx+1,cy-1)
   // right. Diagonals sum and are normalised so diagonal speed == cardinal.
   Flt dx=0, dy=0;
   if(Kb.b(KB_UP   )) {dx-=1; dy-=1;}
   if(Kb.b(KB_DOWN )) {dx+=1; dy+=1;}
   if(Kb.b(KB_LEFT )) {dx-=1; dy+=1;}
   if(Kb.b(KB_RIGHT)) {dx+=1; dy-=1;}
   if(dx!=0 || dy!=0)
   {
      Flt len=Sqrt(dx*dx+dy*dy);
      dx/=len; dy/=len;
      player_x+=dx*SPEED*Time.d();
      player_y+=dy*SPEED*Time.d();
      // stay on the plane (half-cell margin so the dot never leaves it)
      player_x=Clamp(player_x, 0.5f, GRID-0.5f);
      player_y=Clamp(player_y, 0.5f, GRID-0.5f);
   }
   return true;
}

/******************************************************************************/
void Draw()
{
   D.clear(BLACK);

   // Flat isometric plane: 16x16 filled diamonds, checkerboard.
   for(Int i=0; i<GRID; i++)
      for(Int j=0; j<GRID; j++)
      {
         Vec2 c=worldToScreen(j+0.5f, i+0.5f);
         Quad2 diamond(
            Vec2(c.x,            c.y-TILE_H*0.5f), // top
            Vec2(c.x+TILE_W*0.5f, c.y           ), // right
            Vec2(c.x,            c.y+TILE_H*0.5f), // bottom
            Vec2(c.x-TILE_W*0.5f, c.y           )  // left
         );
         Color col=((i+j)&1) ? Color(150, 130, 100) : Color(180, 160, 120);
         diamond.draw(col, true);
      }

   // The player: a dot, drawn at the smooth (sub-cell) position.
   Vec2 p=worldToScreen(player_x, player_y);
   D.dot(GREEN, p.x, p.y, 0.025f);

   // HUD: title, FPS, position, controls.
   // D.text centres the string on x, so centre the HUD on screen (x=0);
   // left-aligning via a negative x cut the long lines off-screen.
   D.text(0.0f,  0.92f, S+"Rings of Power - Tribute (Classic Isometric, M7 2D)");
   D.text(0.0f,  0.84f, S+"FPS: "+Time.fps());
   D.text(0.0f,  0.76f, S+"Player cell: ("+player_x+", "+player_y+")");
   D.text(0.0f, -0.92f, S+"Arrow keys walk the dot - ESC quits");
}

/******************************************************************************/
