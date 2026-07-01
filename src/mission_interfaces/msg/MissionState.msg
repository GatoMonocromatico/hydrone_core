# Estado atual da missao (T10.2 - item a).
std_msgs/Header header          # stamp p/ medir latencia
string vehicle                  # hydrone ou whiteboat
string phase                    # fase: IDLE, TAKEOFF, ENROUTE, HOLD, RTL
uint32 current_waypoint         # waypoint atual
geometry_msgs/Point target_position   # posicao alvo (ENU x/y/z ou lat/lon/alt)
