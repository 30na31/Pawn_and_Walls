import pygame
import sys

pygame.init()
WIDTH, HEIGHT = 800, 600
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Name Entry")

FONT = pygame.font.SysFont(None, 28)
BIG = pygame.font.SysFont(None, 36)

# Colors
BG = (235, 235, 240)
TEXT = (20, 20, 20)
LABEL = (90, 90, 90)
BORDER_ACTIVE = (50, 120, 220)
BORDER_INACTIVE = (150, 150, 160)
BUTTON_BG = (70, 130, 180)
BUTTON_TEXT = (255, 255, 255)
INPUT_BG = (255, 255, 255)

# UI layout (top-centered group)
input_w, input_h = 360, 44
button_w, button_h = 140, 44

label_surf = FONT.render("Username", True, LABEL)
# Top-center label
label_pos = (WIDTH // 2 - label_surf.get_width() // 2, 24)

input_rect = pygame.Rect(0, 0, input_w, input_h)
input_rect.centerx = WIDTH // 2
input_rect.top = label_pos[1] + label_surf.get_height() + 12

button_rect = pygame.Rect(0, 0, button_w, button_h)
button_rect.centerx = WIDTH // 2
button_rect.top = input_rect.bottom + 12

active = False
text = ""

clock = pygame.time.Clock()

def submit(name_value: str):
    pass

while True:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            pygame.quit()
            sys.exit()

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if input_rect.collidepoint(event.pos):
                active = True
            else:
                active = False

            if button_rect.collidepoint(event.pos):
                submit(text)

        if event.type == pygame.KEYDOWN and active:
            if event.key == pygame.K_RETURN:
                submit(text)
            elif event.key == pygame.K_BACKSPACE:
                text = text[:-1]
            else:
                # Append printable character
                if event.unicode.isprintable():
                    text += event.unicode

    screen.fill(BG)

    # Label
    screen.blit(label_surf, label_pos)

    # Input box
    pygame.draw.rect(screen, INPUT_BG, input_rect, border_radius=6)
    pygame.draw.rect(
        screen,
        BORDER_ACTIVE if active else BORDER_INACTIVE,
        input_rect,
        width=2,
        border_radius=6
    )
    txt_surf = BIG.render(text, True, TEXT)
    # Keep text inside the box
    clip = txt_surf.get_rect()
    clip.width = input_rect.width - 12
    screen.set_clip(input_rect.inflate(-12, -8))
    screen.blit(txt_surf, (input_rect.x + 8, input_rect.y + 6))
    screen.set_clip(None)

    # Submit button
    pygame.draw.rect(screen, BUTTON_BG, button_rect, border_radius=6)
    btn_text = FONT.render("Submit", True, BUTTON_TEXT)
    screen.blit(
        btn_text,
        (button_rect.centerx - btn_text.get_width() // 2,
         button_rect.centery - btn_text.get_height() // 2))
    pygame.display.flip()
    clock.tick(60)  