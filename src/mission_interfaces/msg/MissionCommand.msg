# Comando do planejador p/ um veiculo (T10.2 - item b).
std_msgs/Header header          # stamp p/ medir latencia
string vehicle                  # veiculo alvo: hydrone ou whiteboat
string command                  # GOTO, HOLD, ARM, TAKEOFF, RTL
uint32 waypoint                 # waypoint alvo
geometry_msgs/Point target_position   # posicao alvo (ENU x/y/z ou lat/lon/alt)
