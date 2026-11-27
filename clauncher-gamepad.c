/* Feed CLauncher's GLFW gamepad slot from the system's SDL2 mappings. */
#include <dlfcn.h>
#include <SDL.h>
#define GLFW_INCLUDE_NONE
#include <GLFW/glfw3.h>

static SDL_GameController *controllers[16];

static void map_left_stick(GLFWgamepadstate *state)
{
    float x = state->axes[GLFW_GAMEPAD_AXIS_LEFT_X];
    float y = state->axes[GLFW_GAMEPAD_AXIS_LEFT_Y];
    state->buttons[GLFW_GAMEPAD_BUTTON_DPAD_LEFT] |= x < -0.55f;
    state->buttons[GLFW_GAMEPAD_BUTTON_DPAD_RIGHT] |= x > 0.55f;
    state->buttons[GLFW_GAMEPAD_BUTTON_DPAD_UP] |= y < -0.55f;
    state->buttons[GLFW_GAMEPAD_BUTTON_DPAD_DOWN] |= y > 0.55f;
}

static int read_sdl(GLFWgamepadstate *state)
{
    static int initialized;
    if (!initialized) {
        SDL_SetHint(SDL_HINT_JOYSTICK_ALLOW_BACKGROUND_EVENTS, "1");
        initialized = SDL_InitSubSystem(SDL_INIT_GAMECONTROLLER) == 0 ? 1 : -1;
    }
    if (initialized < 0)
        return GLFW_FALSE;

    SDL_GameControllerUpdate();
    for (size_t slot = 0; slot < SDL_arraysize(controllers); ++slot) {
        if (controllers[slot] && !SDL_GameControllerGetAttached(controllers[slot])) {
            SDL_GameControllerClose(controllers[slot]);
            controllers[slot] = NULL;
        }
    }
    const int count = SDL_NumJoysticks();
    for (int index = 0; index < count; ++index) {
        if (!SDL_IsGameController(index)
            || SDL_GameControllerFromInstanceID(SDL_JoystickGetDeviceInstanceID(index)))
            continue;
        for (size_t slot = 0; slot < SDL_arraysize(controllers); ++slot) {
            if (!controllers[slot]) {
                controllers[slot] = SDL_GameControllerOpen(index);
                break;
            }
        }
    }

    const SDL_GameControllerButton buttons[] = {
        SDL_CONTROLLER_BUTTON_A, SDL_CONTROLLER_BUTTON_B,
        SDL_CONTROLLER_BUTTON_X, SDL_CONTROLLER_BUTTON_Y,
        SDL_CONTROLLER_BUTTON_LEFTSHOULDER, SDL_CONTROLLER_BUTTON_RIGHTSHOULDER,
        SDL_CONTROLLER_BUTTON_BACK, SDL_CONTROLLER_BUTTON_START,
        SDL_CONTROLLER_BUTTON_GUIDE, SDL_CONTROLLER_BUTTON_LEFTSTICK,
        SDL_CONTROLLER_BUTTON_RIGHTSTICK, SDL_CONTROLLER_BUTTON_DPAD_UP,
        SDL_CONTROLLER_BUTTON_DPAD_RIGHT, SDL_CONTROLLER_BUTTON_DPAD_DOWN,
        SDL_CONTROLLER_BUTTON_DPAD_LEFT,
    };
    *state = (GLFWgamepadstate){0};
    state->axes[GLFW_GAMEPAD_AXIS_LEFT_TRIGGER] = -1.0f;
    state->axes[GLFW_GAMEPAD_AXIS_RIGHT_TRIGGER] = -1.0f;
    int found = GLFW_FALSE;
    for (size_t slot = 0; slot < SDL_arraysize(controllers); ++slot) {
        SDL_GameController *controller = controllers[slot];
        if (!controller)
            continue;
        found = GLFW_TRUE;
        for (size_t button = 0; button < SDL_arraysize(buttons); ++button)
            state->buttons[button] |= SDL_GameControllerGetButton(controller, buttons[button]);
        for (int axis = GLFW_GAMEPAD_AXIS_LEFT_X; axis <= GLFW_GAMEPAD_AXIS_RIGHT_Y; ++axis) {
            Sint16 raw = SDL_GameControllerGetAxis(controller, (SDL_GameControllerAxis)axis);
            float value = raw / (raw < 0 ? 32768.0f : 32767.0f);
            if (SDL_fabsf(value) > SDL_fabsf(state->axes[axis]))
                state->axes[axis] = value;
        }
        for (int axis = GLFW_GAMEPAD_AXIS_LEFT_TRIGGER; axis <= GLFW_GAMEPAD_AXIS_RIGHT_TRIGGER; ++axis) {
            float value = SDL_GameControllerGetAxis(controller, (SDL_GameControllerAxis)axis) / 16383.5f - 1.0f;
            if (value > state->axes[axis])
                state->axes[axis] = value;
        }
    }
    return found;
}

int glfwGetGamepadState(int joystick, GLFWgamepadstate *state)
{
    GLFWwindow *(*current_context)(void) = dlsym(RTLD_NEXT, "glfwGetCurrentContext");
    int (*get_attribute)(GLFWwindow *, int) = dlsym(RTLD_NEXT, "glfwGetWindowAttrib");
    GLFWwindow *window = current_context ? current_context() : NULL;
    if (!state || !window || !get_attribute)
        return GLFW_FALSE;
    if (!get_attribute(window, GLFW_FOCUSED)) {
        *state = (GLFWgamepadstate){0};
        state->axes[GLFW_GAMEPAD_AXIS_LEFT_TRIGGER] = -1.0f;
        state->axes[GLFW_GAMEPAD_AXIS_RIGHT_TRIGGER] = -1.0f;
        return GLFW_TRUE;
    }
    if (joystick == GLFW_JOYSTICK_1 && read_sdl(state)) {
        map_left_stick(state);
        return GLFW_TRUE;
    }

    int (*native_state)(int, GLFWgamepadstate *) = dlsym(RTLD_NEXT, "glfwGetGamepadState");
    for (int index = joystick; native_state && index <= GLFW_JOYSTICK_LAST; ++index) {
        if (native_state(index, state)) {
            map_left_stick(state);
            return GLFW_TRUE;
        }
    }
    return GLFW_FALSE;
}
