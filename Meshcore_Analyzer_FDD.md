# Meshcore Network Analyzer

## High Level Target description

The goal is to have a web application that visualizes traffic and signal strength between repeaters of the meshcore network on a map. This data should be captured by listening to the traffic and actively probing the network with trace commands.

meshcore uses a public key to identify nodes. To save air time, only the first byte of those keys is used to describe a path through the repeaters.

## Architecture

The solution should of the following three components:

### 1\. Listener/ Network node

This component is connected to a physical hardware through USB and can be remote controlled through that USB interface. In a broader setup this component may be instantiated across the network in different locations.

Tasks:

- Interact with the meshcore node
- Get all contacts, filtered by repeaters in the list
- Listen to all packets and extract the path information were possible
- be able to send trace messages if needed
- 2send all gathered contacts to the “processing” component (see [Meshcore Network Analyzer](Meshcore%20Network%20Analyzer.md))
- Retrieve commands from the processing competent to execute traces
- Handle in between disconnects from the device, to pull for missed messages or contacts
- Interaction between this and the processing component should be done through a rest service
- all information should be UTC timestamped

This component should be written in python using a venv environment and prepared to be shipped as a docker container.

In a production scenario this would be run on a raspberry

### 2\. Processing

This is the central component with integrates data storage with the business logic. I should communicate the other components via a REST service.

Tasks:

- all contacts and path should be stored
- logic to build a graph with the repeaters being the nodes of the graph and the path information creating the connections between the nodes. The nodes should contain the following attributes: number of messages per week between those and a SNR signal rating
- Since meshcore only uses the first byte of the public key of the repeaters to specify a path more than one repeater could be a match. To solve this a function for to determine the right repeater is needed. Since we have the GPS coordinates choosing the one with the least distance to the other repeaters in the same path should solve this
- Information can be delivered from various “listener/ Network node” componets which my be at different GPS locations. This must be taken into account for the data storage and the graph buildup
- To verify the graph connection this component should ask the relevant “listener/ Network node” instance to run a trace. Since traces have to start and end with the nearest repeater, choosing the node which can easily reach the path member should be selected. To avoid flooding the network there should be a throttle of 30 se3condfs between traces. Generally the trace scheduling should take place so that we can verify path once a day
- Claude should choose a storage the data that provides the max performance
- Access and controlling the logic should be possible over the rest service. This should include all parameters and a scheduling overview for the traces. A possibility to hold the traces schedule and some statistics
- in shipment this component should also be a docker container
- API key authentication should be implemented for the REST interface. Also all “Listener/ Network node” need a seperate API key and a table to be stored

### 3\. Visualization

This component is a web application that visualizes the data from the processing component.

Tasks:

- Administration part to administer the processing unit, like seeing statistics, setting API keys, seeing the trace schedule and patameters
- Main focus: Showing the repeaters on the openstreetmap with drawn lines between them representing the graph. The line thickness should indicate the number of messages and the color the SNR raring (low = red to green for good values like 12)
- 

## Knowledge/ Specifications

### What is MeshCore?

MeshCore is a multi platform system for enabling secure text based communications utilising LoRa radio hardware. It can be used for Off-Grid Communication, Emergency Response & Disaster Recovery, Outdoor Activities, Tactical Security including law enforcement and private security and also IoT sensor networks.

### Python Lib/ bindings to use with an external device

[meshcore-dev/meshcore_py: Python bindings for meshcore](https://github.com/meshcore-dev/meshcore_py)

### Specifications folder

the “specifications” folder within the project directory holds addional information regarding meshcore and the packet structure.