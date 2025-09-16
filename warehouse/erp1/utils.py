import math
def haversine_distance_m(lat1,lng1,lat2,lng2):
    if None in (lat1,lng1,lat2,lng2): return None
    R=6371000.0
    from math import radians, sin, cos, atan2, sqrt
    phi1=radians(float(lat1)); phi2=radians(float(lat2))
    dphi=radians(float(lat2)-float(lat1)); dl=radians(float(lng2)-float(lng1))
    a=sin(dphi/2)**2+cos(phi1)*cos(phi2)*sin(dl/2)**2
    c=2*atan2(sqrt(a),sqrt(1-a))
    return int(round(R*c))
