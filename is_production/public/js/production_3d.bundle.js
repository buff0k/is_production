import * as THREE from "three";

frappe.provide("is_production");

is_production.THREE = THREE;

console.log("Three.js loaded", THREE.REVISION);
