
class cleaner:

    def __init__(self, parameters):
        self.parameters = parameters

        if self.parameters['clean_type'] == 'break_at_intersections':
            qf = self.parameters['fMap']
            attr_dict = qf.get_attr_dict(self.parameters['attr_index'])
            geom_dict_indices = qf.get_geom_vertices_dict(self.parameters['attr_index'])
            new_field = QgsField('broken_id', QVariant.String)
            fid = qf.uid_to_fid(self.parameters['attr_index'])

            feat_to_add = []
            count = 1
            feat_to_brk = []
            for k, v in self.parameters['breakages']:
                # add first and last vertex
                v = list(v)
                v.append(0)
                v.append(len(geom_dict_indices[k])-1)
                v = list(set(v))
                v.sort()
                count_2 = 1
                for ind, index in enumerate(v):
                    if ind != len(v) - 1:
                        points = [QgsGeometry.fromPoint(geom_dict_indices[k][i]).asPoint() for i in range(index, v[ind + 1] + 1)]
                        new_geom = QgsGeometry().fromPolyline(points)
                        new_feat = QgsFeature()
                        new_feat.setGeometry(new_geom)
                        new_feat.setAttributes(attr_dict[k] + [attr_dict[k][self.parameters['attr_index']] + '-br-' + str(count) + str(count_2)])
                        # new_feat.setFid()
                        count_2 += 1
                        feat_to_add.append(new_feat)
                        count += 1
                feat_to_brk.append(fid[k])

            feat_to_copy = [feat for feat in qf.obj if feat.id() not in feat_to_brk]
            for f in feat_to_copy:
                feat = QgsFeature()
                feat.setAttributes(f.attributes() + [f.attributes()[self.parameters['attr_index']]])
                feat.setGeometry(QgsGeometry.fromWkt(f.attributes()[self.parameters['wkt_index']]))
                feat_to_add.append(feat)

            self.result = feat_to_add, new_field


    def break_sGraph(self, id_column):
        pass


    def merge_sGraph(self, id_column):
        pass


    def dupl_sGraph(self, id_column):
        pass