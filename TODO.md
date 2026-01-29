# Conext and function clarification

## Traces
- traces specify a defined route through the network
- This route also needs to include a way back for the packet, so that our listening node can receive the result
- traces are NOT using flooding - only the specified route is used
- if one of the repeaters in the route is not reachable the whole trace fails
- keeping the trace as short as possible is the goal
- since we capture a lot of pathes we need to figure out a way to cut those into smaller chunks to test and to make "our" best repeater part of it

## Our graph and line attributes
- we defined that the lines should contain attributes like messages per day and SNR. This SNR describes the signal strenth between two repeaters.
- the SNR can only be determined by a trace
- all SNR informaiton in other packets only reflects the last hop, which is our repeater nearby
- in our visualization we should use a dark grey color if we don't have any SNR attribute yet

# TODO

## ~~container~~ ✓ COMPLETED
- ~~build containers should be multiplatform, at least arm and pc platform~~ ✓
- ~~this could affect the dockerfiles and the workflow definition~~ ✓
- Implementation: Added `platforms: linux/amd64,linux/arm64` to all three build jobs in `.github/workflows/build-containers.yml`

## ~~admin web frontend~~ ✓ COMPLETED
- ~~can please extend the admin frontend so that the listener administration can be done from there~~ ✓
- ~~adding listeners and their authentification~~ ✓
- ~~editing and removing as well~~ ✓
- Implementation: Created `ListenersPage.tsx` with full CRUD operations, API key management, and integrated into navigation




