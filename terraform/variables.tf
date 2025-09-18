variable "project_id" {
  description = "GCP project ID"
  type        = string
}

variable "region" {
  description = "GCP region"
  type        = string
  default     = "asia-south1"  
}

variable "credentials_file" {
  description = "Path to GCP credentials JSON file"
  type        = string
}

variable "cluster_name" {
  description = "GKE Cluster name"
  type        = string
  default     = "app-cluster"
}

variable "zone" {
  default = "asia-south1-a" 
}