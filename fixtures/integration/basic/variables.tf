variable "environment_prefix" {
  type        = string
  description = "Prefix passed through to the consumed framework."
}

variable "global_tag" {
  type        = string
  description = "Global tag passed through to the consumed framework."
}

variable "all_environments" {
  type        = any
  description = "Runner-owned environment data passed through to the consumed framework."
}
