(*
 * Copyright (c) Meta Platforms, Inc. and affiliates.
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 *)

module VariableMetadata : sig
  type t = {
    name: Ast.Reference.t;
    type_annotation: Ast.Expression.Expression.t option;
  }
  [@@deriving show, compare]
end

module ModelQueryRegistryMap : sig
  type t

  val empty : t

  val set : t -> model_query_name:string -> models:Registry.t -> t

  val get : t -> string -> Registry.t option

  val merge : model_join:(Model.t -> Model.t -> Model.t) -> t -> t -> t

  val to_alist : t -> (string * Registry.t) list

  val mapi : t -> f:(model_query_name:string -> models:Registry.t -> Registry.t) -> t

  val get_model_query_names : t -> string list

  val get_models : t -> Registry.t list

  val get_registry : model_join:(Model.t -> Model.t -> Model.t) -> t -> Registry.t
end

module DumpModelQueryResults : sig
  val dump_to_string : model_query_results:ModelQueryRegistryMap.t -> string

  val dump_to_file : model_query_results:ModelQueryRegistryMap.t -> path:PyrePath.t -> unit

  val dump_to_file_and_string
    :  model_query_results:ModelQueryRegistryMap.t ->
    path:PyrePath.t ->
    string
end

module CallableQueryExecutor : sig
  val generate_annotations_from_query_on_target
    :  verbose:bool ->
    resolution:Analysis.GlobalResolution.t ->
    class_hierarchy_graph:Interprocedural.ClassHierarchyGraph.SharedMemory.t ->
    target:Interprocedural.Target.t ->
    ModelParseResult.ModelQuery.t ->
    ModelParseResult.ModelAnnotation.t list
end

module AttributeQueryExecutor : sig
  val generate_annotations_from_query_on_target
    :  verbose:bool ->
    resolution:Analysis.GlobalResolution.t ->
    class_hierarchy_graph:Interprocedural.ClassHierarchyGraph.SharedMemory.t ->
    target:VariableMetadata.t ->
    ModelParseResult.ModelQuery.t ->
    ModelParseResult.TaintAnnotation.t list
end

val get_globals_and_annotations : resolution:Analysis.GlobalResolution.t -> VariableMetadata.t list

module GlobalVariableQueryExecutor : sig
  val generate_annotations_from_query_on_target
    :  verbose:bool ->
    resolution:Analysis.GlobalResolution.t ->
    class_hierarchy_graph:Interprocedural.ClassHierarchyGraph.SharedMemory.t ->
    target:VariableMetadata.t ->
    ModelParseResult.ModelQuery.t ->
    ModelParseResult.TaintAnnotation.t list
end

val generate_models_from_queries
  :  resolution:Analysis.GlobalResolution.t ->
  scheduler:Scheduler.t ->
  class_hierarchy_graph:Interprocedural.ClassHierarchyGraph.SharedMemory.t ->
  source_sink_filter:SourceSinkFilter.t option ->
  verbose:bool ->
  callables_and_stubs:Interprocedural.Target.t list ->
  stubs:Interprocedural.Target.t Base.Hash_set.t ->
  ModelParseResult.ModelQuery.t list ->
  ModelQueryRegistryMap.t * ModelVerificationError.t list
