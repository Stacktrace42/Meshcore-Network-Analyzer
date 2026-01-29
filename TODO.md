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

## Traces
### Running logic
- currently we specify juat a source and target, which does not make sense. We need to modify this to adhere to the trace logic and align this wich chunks from our captured path. Also the way back for the packets should be defined. 
- the trace logic should be part of the processing component since it should distirbute trace through many listners. Those having leading to a shorter trace patch should execute those. We should also store the calculated trace path in the trace table and visualize it in the frontend
- Generally we should look into all pathes we have collected, breack them down into viable traces. This list could be further reduced because some traces may be a subset of others.
- Before we add traces to the schedule we must chek if those are alreay in there. The list should not grow if we can't execute it.
- the paramters for the throtteling (TRACE_THROTTLE_SECONDS) should be sotred in teh db and changeable thorugh the web frontend in the admin part
- the trace listing should also be a pageable table in the web frontend
- the trace path should be shown

### graph
- reapters that don't have a GPS coordinate are currently filtered out which we should do only for reapters that we don't have any path information. For all others we should assign a dark organe color and try to triangulate their position from the path information: We create a list of all neighbours of that reapeter for which we know the coordiantes and then calculate the middle point. it won't be exact but much better than not showing them.
- currently we stored the SNR also determined by other messages which is wrong since they only show the SNR of the last hop. This need correction: We need to null all current values. Those should later be updated by the reponses from the trace where we get a SNR value per hop.
- Also one thing I would like you to check: Currently we only have one repater 94, so we assinged all trace to this repater, but I know there is a second one nearerby which has not yet been captured by the device. If that would happen would our graph information automatically corrected? (and yes it should be)

## github
- I created an empty repository on github. Can you uplaod everything there? 
- https://github.com/Stacktrace42/Meshcore-Network-Analyzer.git
- let me know if i need to do something about authentification since this is a private repo 

## docker#
the current docker compose file also creates information for the building part. But if we want other people to contribute to our database we need to make it simpler. So ideally I would like to provide pre-build containers on the github registry. What would you recommend, having a "build" and "runtime" docker-compose?


