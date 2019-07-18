import pygame
import pygame.locals

clock = pygame.time.Clock()

running = True
screen = pygame.display.set_mode((300, 300))

while running:
    clock.tick(30)
    screen.fill((100, 200, 100))
    for event in pygame.event.get():
        if event.type == pygame.QUIT or event.type == pygame.locals.QUIT:
            pygame.quit()
    pygame.display.update()