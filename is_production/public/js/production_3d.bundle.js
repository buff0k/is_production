import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";

frappe.provide("is_production");

is_production.THREE = THREE;
is_production.OrbitControls = OrbitControls;

console.log("Three.js loaded", THREE.REVISION);